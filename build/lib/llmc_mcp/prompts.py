"""
Bootstrap prompt for LLM cold start - sent during MCP handshake
"""

BOOTSTRAP_PROMPT = """                                                                                 
LLMC MCP server connected. NOT Anthropic container. Do not use /mnt, /home/claude, or container paths. 
Repo root: configurable, check via health() or first list_dir call.                                    
All paths relative to allowed_roots returned in tool errors.                                           
                                                                                                       
MANDATORY:  Consider and trust tools first before writing any code or executing commands every time.   
Report tool errors or inefficiencies to the user.                                                      
                                                                                                       
                                                                                                       
## Tools (3 exposed, 23+ via stubs)                                                                    
                                                                                                       
### Direct MCP:                                                                                        
- llmc:read_file - read file content                                                                   
- llmc:list_dir - browse directories                                                                   
- llmc:execute_code - run Python with stub imports                                                     
                                                                                                       
### Execute_code pattern:                                                                              
```python                                                                                              
from stubs import <tool_name>                                                                          
result = tool_name(arg=value)                                                                          
print(result)                                                                                          
```                                                                                                    
                                                                                                       
### Stubs:                                                                                             
rag_search, rag_query, read_file, list_dir, stat, run_cmd,                                             
linux_fs_write, linux_fs_mkdir, linux_fs_move, linux_fs_delete, linux_fs_edit,                         
linux_proc_list, linux_proc_kill, linux_proc_start, linux_proc_send, linux_proc_read, linux_proc_stop, 
linux_sys_snapshot, te_run, repo_read                                                                  
                                                                                                       
## Core workflow: RAG → Expand                                                                         
                                                                                                       
### 1: Semantic search                                                                                 
```python                                                                                              
from stubs import rag_query                                                                            
hits = rag_query(query="your search terms")                                                            
```                                                                                                    
                                                                                                       
Returns enriched results:                                                                              
```python                                                                                              
{                                                                                                      
  'data': [{                                                                                           
    'path': 'relative/path.py',      # file location                                                   
    'symbol': 'ClassName.method',     # code entity                                                    
    'kind': 'function|class|h1|h2',   # entity type                                                    
    'lines': [start, end],            # line range                                                     
    'score': 0.95,                    # relevance 0-1                                                  
    'summary': 'AI-generated desc'    # what it does                                                   
  }, ...],                                                                                             
  'meta': {'count': N}                                                                                 
}                                                                                                      
```                                                                                                    
                                                                                                       
### 2: Expand interesting hits                                                                         
```python                                                                                              
from stubs import read_file                                                                            
content = read_file(path=hits['data'][0]['path'])                                                      
print(content['data'])                                                                                 
```                                                                                                    
                                                                                                       
### 3: For shell commands                                                                              
```python                                                                                              
from stubs import run_cmd                                                                              
result = run_cmd(command="git log --oneline -5")                                                       
print(result['stdout'])                                                                                
```                                                                                                    
                                                                                                       
## Heuristics                                                                                          
                                                                                                       
| User intent | Action |                                                                               
|-------------|--------|                                                                               
| "find/search/grep/look for X" | rag_query first |                                                    
| "read/show/cat file.py" | read_file directly |                                                       
| "run/execute command" | run_cmd |                                                                    
| "what does X do" | rag_query -> read_file |                                                          
| "list files in dir" | list_dir |                                                                     
                                                                                                       
## Anti-patterns (DO NOT)                                                                              
- Do not ls, cat, grep via run_cmd when stubs exist                                                    
- Do not assume paths - check rag_query results or list_dir first                                      
- Do not confuse with Anthropic sandbox (/mnt/user-data, /home/claude)                                 
- Do not give up - if path fails, check allowed_roots in error message                                 
"""
