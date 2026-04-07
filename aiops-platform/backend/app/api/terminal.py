#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Web Terminal API
通过 WebSocket 实现终端功能
"""

import os
import sys
import json
import asyncio
import subprocess
import pty
import signal
import struct
import fcntl
import termios
from typing import Optional
from fastapi import WebSocket, WebSocketDisconnect


class TerminalSession:
    """终端会话管理"""
    
    def __init__(self):
        self.master_fd: Optional[int] = None
        self.slave_fd: Optional[int] = None
        self.process: Optional[subprocess.Popen] = None
        self.current_dir: str = os.getcwd()
        self.env: dict = os.environ.copy()
        self.connected: bool = False
        
    async def start(self, rows: int = 24, cols: int = 80):
        """启动终端会话"""
        print(f"[Terminal] Starting session in {self.current_dir}", file=sys.stderr)
        
        self.master_fd, self.slave_fd = pty.openpty()
        
        self._set_terminal_size(rows, cols)
        
        self.process = subprocess.Popen(
            ["/bin/zsh", "-i"],
            stdin=self.slave_fd,
            stdout=self.slave_fd,
            stderr=self.slave_fd,
            cwd=self.current_dir,
            env=self.env,
            start_new_session=True
        )
        
        print(f"[Terminal] Process started with PID: {self.process.pid}", file=sys.stderr)
        
        os.close(self.slave_fd)
        self.slave_fd = None
        self.connected = True
        
    def _set_terminal_size(self, rows: int, cols: int):
        """设置终端大小"""
        if self.master_fd:
            winsize = struct.pack('HHHH', rows, cols, 0, 0)
            fcntl.ioctl(self.master_fd, termios.TIOCSWINSZ, winsize)
            
    async def resize(self, rows: int, cols: int):
        """调整终端大小"""
        self._set_terminal_size(rows, cols)
        
    async def write(self, data: str):
        """向终端写入数据"""
        if self.master_fd is not None:
            try:
                os.write(self.master_fd, data.encode('utf-8'))
            except OSError as e:
                print(f"[Terminal] Write error: {e}", file=sys.stderr)
                
    async def read(self) -> Optional[str]:
        """从终端读取数据"""
        if self.master_fd is None:
            return None
            
        try:
            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(None, os.read, self.master_fd, 4096)
            if data:
                return data.decode('utf-8', errors='replace')
            return None
        except Exception as e:
            print(f"[Terminal] Read error: {e}", file=sys.stderr)
            return None
            
    async def close(self):
        """关闭终端会话"""
        self.connected = False
        
        if self.process:
            try:
                os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
                self.process.wait(timeout=2)
            except:
                try:
                    os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
                except:
                    pass
                    
        if self.master_fd is not None:
            try:
                os.close(self.master_fd)
            except:
                pass
            self.master_fd = None


async def websocket_terminal(websocket: WebSocket):
    """
    WebSocket 终端处理
    
    消息格式:
    - 输入: {"type": "input", "data": "command"}
    - 调整大小: {"type": "resize", "rows": 24, "cols": 80}
    - 输出: {"type": "output", "data": "result"}
    """
    print("[Terminal] New WebSocket connection", file=sys.stderr)
    await websocket.accept()
    
    session = TerminalSession()
    output_task = None
    
    try:
        await session.start(rows=24, cols=80)
        print(f"[Terminal] Session started", file=sys.stderr)
        
        welcome_msg = "\r\n\x1b[1;32mWelcome to AIOps Web Terminal\x1b[0m\r\n"
        welcome_msg += f"\x1b[1;34mCurrent Directory: {session.current_dir}\x1b[0m\r\n"
        welcome_msg += "\x1b[90mType commands to interact\x1b[0m\r\n\r\n"
        await websocket.send_json({"type": "output", "data": welcome_msg})
        
        output_task = asyncio.create_task(send_output(websocket, session))
        
        while True:
            try:
                message = await asyncio.wait_for(websocket.receive_text(), timeout=0.1)
            except asyncio.TimeoutError:
                if session.process and session.process.poll() is not None:
                    print("[Terminal] Process exited", file=sys.stderr)
                    break
                continue
                
            try:
                data = json.loads(message)
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "data": "Invalid JSON message"
                })
                continue
            
            msg_type = data.get("type")
            
            if msg_type == "input":
                input_data = data.get("data", "")
                await session.write(input_data)
                
            elif msg_type == "resize":
                rows = data.get("rows", 24)
                cols = data.get("cols", 80)
                await session.resize(rows, cols)
                
            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})
                
    except WebSocketDisconnect:
        print("[Terminal] WebSocket disconnected", file=sys.stderr)
    except Exception as e:
        print(f"[Terminal] Session error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        try:
            await websocket.send_json({
                "type": "error",
                "data": f"Terminal error: {str(e)}"
            })
        except:
            pass
            
    finally:
        print("[Terminal] Closing session", file=sys.stderr)
        if output_task:
            output_task.cancel()
        await session.close()


async def send_output(websocket: WebSocket, session: TerminalSession):
    """持续读取终端输出"""
    try:
        while session.connected:
            data = await session.read()
            if data:
                try:
                    print(f"[Terminal] Sending output: {repr(data[:100])}", file=sys.stderr)
                    await websocket.send_json({"type": "output", "data": data})
                except Exception as e:
                    print(f"[Terminal] Send error: {e}", file=sys.stderr)
                    break
            else:
                await asyncio.sleep(0.01)
    except asyncio.CancelledError:
        pass
    except Exception as e:
        print(f"[Terminal] Send output error: {e}", file=sys.stderr)
