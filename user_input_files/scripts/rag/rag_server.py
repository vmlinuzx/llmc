#!/usr/bin/env python3
"""
rag_server.py - Web UI and API for RAG system

Usage:
    python rag_server.py
    
Then visit: http://localhost:8765
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, List
from pathlib import Path

from query_context import ContextQuerier, CHROMA_DB_PATH
from index_workspace import WorkspaceIndexer, WORKSPACE_ROOT

app = FastAPI(title="DeepSeek RAG System")

# Initialize
querier = ContextQuerier(CHROMA_DB_PATH)
indexer = WorkspaceIndexer(WORKSPACE_ROOT, CHROMA_DB_PATH)


class QueryRequest(BaseModel):
    query: str
    project: Optional[str] = None
    file_type: Optional[str] = None
    limit: int = 10


class ContextRequest(BaseModel):
    task: str
    project: str
    max_tokens: int = 8000


@app.get("/", response_class=HTMLResponse)
async def root():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>DeepSeek RAG System</title>
        <style>
            * { box-sizing: border-box; margin: 0; padding: 0; }
            body { 
                font-family: 'Segoe UI', sans-serif; 
                background: #1e1e1e; 
                color: #d4d4d4;
                padding: 20px;
            }
            .container { max-width: 1200px; margin: 0 auto; }
            h1 { color: #4ec9b0; margin-bottom: 30px; }
            .search-box {
                background: #252526;
                padding: 30px;
                border-radius: 8px;
                margin-bottom: 30px;
            }
            input, select, button {
                font-size: 16px;
                padding: 12px;
                border: 1px solid #3e3e42;
                border-radius: 4px;
                background: #3c3c3c;
                color: #d4d4d4;
            }
            input[type="text"] { width: 100%; margin-bottom: 15px; }
            button {
                background: #0e639c;
                color: white;
                cursor: pointer;
                border: none;
            }
            button:hover { background: #1177bb; }
            .stats {
                background: #252526;
                padding: 20px;
                border-radius: 8px;
                margin-bottom: 30px;
            }
            .stat-item {
                display: inline-block;
                margin-right: 30px;
            }
            .stat-value {
                color: #4ec9b0;
                font-size: 24px;
                font-weight: bold;
            }
            .results {
                background: #252526;
                padding: 20px;
                border-radius: 8px;
            }
            .result-item {
                background: #1e1e1e;
                padding: 20px;
                border-radius: 4px;
                margin-bottom: 15px;
                border-left: 3px solid #4ec9b0;
            }
            .result-meta {
                color: #858585;
                font-size: 14px;
                margin-bottom: 10px;
            }
            .result-text {
                font-family: 'Consolas', monospace;
                white-space: pre-wrap;
                font-size: 13px;
                line-height: 1.5;
            }
            .relevance {
                background: #0e639c;
                color: white;
                padding: 4px 8px;
                border-radius: 3px;
                font-size: 12px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🧠 DeepSeek RAG System</h1>
            
            <div class="stats" id="stats">
                <div class="stat-item">
                    <div>Total Chunks</div>
                    <div class="stat-value" id="total-chunks">-</div>
                </div>
                <div class="stat-item">
                    <div>Projects</div>
                    <div class="stat-value" id="projects">-</div>
                </div>
                <div class="stat-item">
                    <div>DB Size</div>
                    <div class="stat-value" id="db-size">-</div>
                </div>
            </div>
            
            <div class="search-box">
                <input type="text" id="query" placeholder="Search for code... (e.g., 'authentication system', 'supabase queries')">
                <div style="display: flex; gap: 10px; margin-bottom: 15px;">
                    <input type="text" id="project" placeholder="Project filter (optional)" style="flex: 1;">
                    <input type="text" id="file-type" placeholder="File type (e.g., .ts)" style="flex: 1;">
                    <select id="limit" style="flex: 0.5;">
                        <option value="5">5 results</option>
                        <option value="10" selected>10 results</option>
                        <option value="20">20 results</option>
                        <option value="50">50 results</option>
                    </select>
                </div>
                <button onclick="search()">🔍 Search</button>
                <button onclick="buildContext()" style="background: #16825d;">🤖 Build Context for Task</button>
            </div>
            
            <div class="results" id="results" style="display: none;"></div>
        </div>
        
        <script>
            // Load stats on page load
            fetch('/stats')
                .then(r => r.json())
                .then(data => {
                    document.getElementById('total-chunks').textContent = data.total_chunks.toLocaleString();
                    document.getElementById('projects').textContent = data.projects;
                    document.getElementById('db-size').textContent = data.db_size;
                });
            
            function search() {
                const query = document.getElementById('query').value;
                const project = document.getElementById('project').value || null;
                const fileType = document.getElementById('file-type').value || null;
                const limit = parseInt(document.getElementById('limit').value);
                
                if (!query) {
                    alert('Please enter a search query');
                    return;
                }
                
                fetch('/query', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({query, project, file_type: fileType, limit})
                })
                .then(r => r.json())
                .then(results => {
                    const resultsDiv = document.getElementById('results');
                    resultsDiv.style.display = 'block';
                    
                    if (results.length === 0) {
                        resultsDiv.innerHTML = '<p>No results found</p>';
                        return;
                    }
                    
                    resultsDiv.innerHTML = results.map((r, i) => `
                        <div class="result-item">
                            <div class="result-meta">
                                <strong>${r.metadata.file_path}</strong> 
                                <span class="relevance">Relevance: ${(r.relevance * 100).toFixed(1)}%</span>
                                <br>
                                Project: ${r.metadata.project} | Type: ${r.metadata.file_ext}
                            </div>
                            <div class="result-text">${r.text.substring(0, 500)}${r.text.length > 500 ? '...' : ''}</div>
                        </div>
                    `).join('');
                });
            }
            
            function buildContext() {
                const task = document.getElementById('query').value;
                const project = document.getElementById('project').value;
                
                if (!task || !project) {
                    alert('Please enter both task and project');
                    return;
                }
                
                fetch('/context', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({task, project, max_tokens: 8000})
                })
                .then(r => r.text())
                .then(context => {
                    const resultsDiv = document.getElementById('results');
                    resultsDiv.style.display = 'block';
                    resultsDiv.innerHTML = `
                        <div class="result-item">
                            <div class="result-meta"><strong>Context for Task</strong></div>
                            <div class="result-text">${context}</div>
                        </div>
                    `;
                });
            }
            
            // Enter key to search
            document.getElementById('query').addEventListener('keypress', (e) => {
                if (e.key === 'Enter') search();
            });
        </script>
    </body>
    </html>
    """


@app.get("/stats")
async def get_stats():
    """Get collection statistics"""
    try:
        stats = indexer.get_stats()
        
        # Calculate DB size
        db_size = 0
        for file in Path(CHROMA_DB_PATH).rglob('*'):
            if file.is_file():
                db_size += file.stat().st_size
        
        db_size_mb = db_size / (1024 * 1024)
        
        return {
            "total_chunks": stats["total_chunks"],
            "projects": stats["projects"],
            "project_list": stats["project_list"],
            "db_size": f"{db_size_mb:.1f} MB"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/query")
async def query(request: QueryRequest):
    """Query for relevant code"""
    try:
        results = querier.query(
            request.query,
            project=request.project,
            file_type=request.file_type,
            limit=request.limit
        )
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/context", response_class=HTMLResponse)
async def build_context(request: ContextRequest):
    """Build full context for a task"""
    try:
        context = querier.build_context_for_task(
            request.task,
            request.project,
            max_tokens=request.max_tokens
        )
        return context
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting RAG server...")
    print("📍 Visit: http://localhost:8765")
    uvicorn.run(app, host="0.0.0.0", port=8765)
