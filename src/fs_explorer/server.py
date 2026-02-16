"""
FastAPI server for FsExplorer web UI.

Provides a WebSocket endpoint for real-time workflow streaming
and serves the single-page HTML interface.
"""

from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from .agent import set_index_context, clear_index_context
from .index_config import resolve_db_path
from .storage import DuckDBStorage
from .workflow import (
    workflow,
    InputEvent,
    ToolCallEvent,
    GoDeeperEvent,
    AskHumanEvent,
    HumanAnswerEvent,
    get_agent,
    reset_agent,
)
from .exploration_trace import ExplorationTrace, extract_cited_sources

app = FastAPI(title="FsExplorer", description="AI-powered filesystem exploration")


class TaskRequest(BaseModel):
    """Request model for task submission."""
    task: str
    folder: str = "."
    use_index: bool = False
    db_path: str | None = None


@app.get("/", response_class=HTMLResponse)
async def get_ui():
    """Serve the main UI HTML file."""
    html_path = Path(__file__).parent / "ui.html"
    if html_path.exists():
        return HTMLResponse(content=html_path.read_text(), status_code=200)
    return HTMLResponse(content="<h1>UI not found</h1>", status_code=404)


@app.get("/api/folders")
async def list_folders(path: str = "."):
    """
    List folders in the given path.
    Returns list of folder names and current path info.
    """
    try:
        base_path = Path(path).resolve()
        if not base_path.exists():
            return JSONResponse({"error": "Path not found"}, status_code=404)
        if not base_path.is_dir():
            return JSONResponse({"error": "Not a directory"}, status_code=400)
        
        # Get folders (non-hidden)
        folders = sorted([
            f.name for f in base_path.iterdir()
            if f.is_dir() and not f.name.startswith('.')
        ])
        
        # Get parent path (if not at root)
        parent = str(base_path.parent) if base_path != base_path.parent else None
        
        return {
            "current": str(base_path),
            "parent": parent,
            "folders": folders,
            "files_count": len([f for f in base_path.iterdir() if f.is_file()]),
        }
    except PermissionError:
        return JSONResponse({"error": "Permission denied"}, status_code=403)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.websocket("/ws/explore")
async def websocket_explore(websocket: WebSocket):
    """
    WebSocket endpoint for real-time exploration streaming.
    
    Protocol:
    1. Client sends: {"task": "user question"}
    2. Server streams events: {"type": "...", "data": {...}}
    3. Final event: {"type": "complete", "data": {...}}
    """
    await websocket.accept()
    
    try:
        # Receive the task
        data = await websocket.receive_json()
        task = data.get("task", "")
        folder = data.get("folder", ".")
        use_index = bool(data.get("use_index", False))
        db_path = data.get("db_path")
        index_storage: DuckDBStorage | None = None
        
        if not task:
            await websocket.send_json({
                "type": "error",
                "data": {"message": "No task provided"}
            })
            return
        
        # Validate folder
        folder_path = Path(folder).resolve()
        if not folder_path.exists() or not folder_path.is_dir():
            await websocket.send_json({
                "type": "error",
                "data": {"message": f"Invalid folder: {folder}"}
            })
            return

        clear_index_context()
        if use_index:
            resolved_db_path = resolve_db_path(db_path if isinstance(db_path, str) else None)
            storage = DuckDBStorage(resolved_db_path)
            corpus_id = storage.get_corpus_id(str(folder_path))
            if corpus_id is None:
                await websocket.send_json({
                    "type": "error",
                    "data": {
                        "message": (
                            "No index found for the selected folder. "
                            "Run `explore index <folder>` first."
                        )
                    }
                })
                return
            index_storage = storage
            set_index_context(str(folder_path), resolved_db_path)

        trace = ExplorationTrace(root_directory=str(folder_path))
        
        # Reset agent for fresh state
        reset_agent()
        
        # Send start event
        await websocket.send_json({
            "type": "start",
            "data": {
                "task": task,
                "folder": str(folder_path),
                "use_index": use_index,
            }
        })
        
        # Run the workflow
        step_number = 0
        handler = workflow.run(
            start_event=InputEvent(
                task=task,
                folder=str(folder_path),
                use_index=use_index,
            )
        )
        
        async for event in handler.stream_events():
            if isinstance(event, ToolCallEvent):
                step_number += 1
                resolved_document_path: str | None = None
                if event.tool_name == "get_document":
                    doc_id = event.tool_input.get("doc_id")
                    if (
                        index_storage is not None
                        and isinstance(doc_id, str)
                        and doc_id
                    ):
                        document = index_storage.get_document(doc_id=doc_id)
                        if document and not document["is_deleted"]:
                            resolved_document_path = str(document["absolute_path"])
                trace.record_tool_call(
                    step_number=step_number,
                    tool_name=event.tool_name,
                    tool_input=event.tool_input,
                    resolved_document_path=resolved_document_path,
                )
                await websocket.send_json({
                    "type": "tool_call",
                    "data": {
                        "step": step_number,
                        "tool_name": event.tool_name,
                        "tool_input": event.tool_input,
                        "reason": event.reason,
                    }
                })
                
            elif isinstance(event, GoDeeperEvent):
                step_number += 1
                trace.record_go_deeper(step_number=step_number, directory=event.directory)
                await websocket.send_json({
                    "type": "go_deeper",
                    "data": {
                        "step": step_number,
                        "directory": event.directory,
                        "reason": event.reason,
                    }
                })
                
            elif isinstance(event, AskHumanEvent):
                step_number += 1
                await websocket.send_json({
                    "type": "ask_human",
                    "data": {
                        "step": step_number,
                        "question": event.question,
                        "reason": event.reason,
                    }
                })
                
                # Wait for human response
                response_data = await websocket.receive_json()
                if response_data.get("type") == "human_response":
                    handler.ctx.send_event(
                        HumanAnswerEvent(response=response_data.get("response", ""))
                    )
        
        # Get final result
        result = await handler
        cited_sources = extract_cited_sources(result.final_result)
        
        # Get token usage
        agent = get_agent()
        usage = agent.token_usage
        input_cost, output_cost, total_cost = usage._calculate_cost()
        
        await websocket.send_json({
            "type": "complete",
            "data": {
                "final_result": result.final_result,
                "error": result.error,
                "stats": {
                    "steps": step_number,
                    "api_calls": usage.api_calls,
                    "documents_scanned": usage.documents_scanned,
                    "documents_parsed": usage.documents_parsed,
                    "prompt_tokens": usage.prompt_tokens,
                    "completion_tokens": usage.completion_tokens,
                    "total_tokens": usage.total_tokens,
                    "tool_result_chars": usage.tool_result_chars,
                    "estimated_cost": round(total_cost, 6),
                },
                "trace": {
                    "step_path": trace.step_path,
                    "referenced_documents": trace.sorted_documents(),
                    "cited_sources": cited_sources,
                },
            }
        })
        
    except WebSocketDisconnect:
        pass
    except Exception as e:
        await websocket.send_json({
            "type": "error",
            "data": {"message": str(e)}
        })
    finally:
        clear_index_context()


def run_server(host: str = "127.0.0.1", port: int = 8000):
    """Run the FastAPI server."""
    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_server()
