import { useEffect, useRef, useState } from 'react';
import { Input, Button, Space, message, Select, Tooltip } from 'antd';
import { 
  PlayCircleOutlined, 
  ClearOutlined, 
  FullscreenOutlined,
  CopyOutlined
} from '@ant-design/icons';
import { Terminal as XTerminal } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import { WebLinksAddon } from '@xterm/addon-web-links';
import '@xterm/xterm/css/xterm.css';
import './Terminal.css';
import { useTerminal } from '../contexts/TerminalContext';

const { Option } = Select;

const Terminal: React.FC = () => {
  const terminalRef = useRef<HTMLDivElement>(null);
  const xtermRef = useRef<XTerminal | null>(null);
  const fitAddonRef = useRef<FitAddon | null>(null);
  const [command, setCommand] = useState('');
  const [theme, setTheme] = useState('dark');
  const [fontSize, setFontSize] = useState(14);

  const { connected, connecting, connect, disconnect, sendCommand, registerTerminal, unregisterTerminal } = useTerminal();

  const themes = {
    dark: {
      background: '#1e1e1e',
      foreground: '#d4d4d4',
      cursor: '#d4d4d4',
      cursorAccent: '#1e1e1e',
      selection: 'rgba(255, 255, 255, 0.3)',
      black: '#000000',
      red: '#cd3131',
      green: '#0dbc79',
      yellow: '#e5e510',
      blue: '#2472c8',
      magenta: '#bc3fbc',
      cyan: '#11a8cd',
      white: '#e5e5e5',
      brightBlack: '#666666',
      brightRed: '#f14c4c',
      brightGreen: '#23d18b',
      brightYellow: '#f5f543',
      brightBlue: '#3b8eea',
      brightMagenta: '#d670d6',
      brightCyan: '#29b8db',
      brightWhite: '#e5e5e5',
    },
    light: {
      background: '#ffffff',
      foreground: '#333333',
      cursor: '#333333',
      cursorAccent: '#ffffff',
      selection: 'rgba(0, 0, 0, 0.3)',
      black: '#000000',
      red: '#cd3131',
      green: '#00bc00',
      yellow: '#949800',
      blue: '#0451a5',
      magenta: '#bc05bc',
      cyan: '#0598bc',
      white: '#555555',
      brightBlack: '#666666',
      brightRed: '#cd3131',
      brightGreen: '#14ce14',
      brightYellow: '#b5ba00',
      brightBlue: '#0451a5',
      brightMagenta: '#bc05bc',
      brightCyan: '#0598bc',
      brightWhite: '#a5a5a5',
    },
  };

  useEffect(() => {
    const timer = setTimeout(() => {
      initTerminal();
    }, 0);
    
    return () => {
      clearTimeout(timer);
      unregisterTerminal();
    };
  }, []);

  useEffect(() => {
    if (xtermRef.current) {
      xtermRef.current.options.theme = themes[theme as keyof typeof themes];
    }
  }, [theme]);

  useEffect(() => {
    if (xtermRef.current) {
      xtermRef.current.options.fontSize = fontSize;
      fitAddonRef.current?.fit();
    }
  }, [fontSize]);

  const initTerminal = () => {
    if (!terminalRef.current) {
      console.error('[Terminal] terminalRef.current is null');
      return;
    }

    console.log('[Terminal] Initializing terminal...');

    const terminal = new XTerminal({
      theme: themes[theme as keyof typeof themes],
      fontFamily: 'Menlo, Monaco, "Courier New", monospace',
      fontSize: fontSize,
      cursorBlink: true,
      cursorStyle: 'block',
      scrollback: 10000,
      allowTransparency: true,
      convertEol: true,
    });

    const fitAddon = new FitAddon();
    const webLinksAddon = new WebLinksAddon();

    terminal.loadAddon(fitAddon);
    terminal.loadAddon(webLinksAddon);

    terminal.open(terminalRef.current);
    
    console.log('[Terminal] Terminal opened');

    requestAnimationFrame(() => {
      fitAddon.fit();
      console.log('[Terminal] Fit addon applied');
    });

    xtermRef.current = terminal;
    fitAddonRef.current = fitAddon;

    terminal.writeln('\x1b[1;32mWelcome to AIOps Web Terminal\x1b[0m');
    terminal.writeln('');
    terminal.writeln('\x1b[90mClick "Connect" to start\x1b[0m');

    registerTerminal(terminal, fitAddon);
  };

  const handleConnect = () => {
    xtermRef.current?.clear();
    xtermRef.current?.writeln('\x1b[1;32mWelcome to AIOps Web Terminal\x1b[0m');
    xtermRef.current?.writeln('');
    xtermRef.current?.writeln('\x1b[90mConnecting...\x1b[0m');
    connect();
    
    setTimeout(() => {
      fitAddonRef.current?.fit();
      xtermRef.current?.focus();
    }, 100);
  };

  const handleDisconnect = () => {
    disconnect();
    xtermRef.current?.writeln('\x1b[1;33mDisconnected\x1b[0m');
  };

  const clearTerminal = () => {
    xtermRef.current?.clear();
  };

  const executeCommand = () => {
    if (command.trim() && connected) {
      sendCommand(command + '\n');
      setCommand('');
    }
  };

  const copyContent = () => {
    const selection = xtermRef.current?.getSelection();
    if (selection) {
      navigator.clipboard.writeText(selection);
      message.success('Copied to clipboard');
    } else {
      message.info('No selection to copy');
    }
  };

  const toggleFullscreen = () => {
    if (terminalRef.current) {
      if (document.fullscreenElement) {
        document.exitFullscreen();
      } else {
        terminalRef.current.requestFullscreen();
      }
    }
  };

  return (
    <div style={{ 
      display: 'flex', 
      flexDirection: 'column', 
      height: '100%',
      overflow: 'hidden'
    }}>
      {/* 工具栏 */}
      <div style={{ 
        padding: '8px 16px', 
        borderBottom: '1px solid #f0f0f0',
        backgroundColor: '#fff',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        flexShrink: 0
      }}>
        <Space>
          <span style={{ fontWeight: 500 }}>Web Terminal</span>
          <span style={{ 
            fontSize: 12, 
            color: connected ? '#52c41a' : connecting ? '#faad14' : '#999',
          }}>
            {connected ? '● Connected' : connecting ? '● Connecting...' : '○ Disconnected'}
          </span>
        </Space>
        
        <Space>
          <Select 
            value={theme} 
            onChange={setTheme}
            style={{ width: 90 }}
            size="small"
          >
            <Option value="dark">Dark</Option>
            <Option value="light">Light</Option>
          </Select>
          
          <Select 
            value={fontSize} 
            onChange={setFontSize}
            style={{ width: 70 }}
            size="small"
          >
            <Option value={12}>12px</Option>
            <Option value={14}>14px</Option>
            <Option value={16}>16px</Option>
          </Select>

          <Tooltip title="Copy">
            <Button 
              size="small" 
              icon={<CopyOutlined />} 
              onClick={copyContent}
            />
          </Tooltip>
          
          <Tooltip title="Clear">
            <Button 
              size="small" 
              icon={<ClearOutlined />} 
              onClick={clearTerminal}
            />
          </Tooltip>
          
          <Tooltip title="Fullscreen">
            <Button 
              size="small" 
              icon={<FullscreenOutlined />} 
              onClick={toggleFullscreen}
            />
          </Tooltip>
          
          {connected ? (
            <Button 
              size="small" 
              danger 
              onClick={handleDisconnect}
            >
              Disconnect
            </Button>
          ) : (
            <Button 
              size="small" 
              type="primary" 
              icon={<PlayCircleOutlined />}
              onClick={handleConnect}
              loading={connecting}
            >
              Connect
            </Button>
          )}
        </Space>
      </div>

      {/* 终端区域 */}
      <div 
        ref={terminalRef} 
        className="terminal-container"
        style={{ 
          flex: 1,
          minHeight: 0,
          backgroundColor: themes[theme as keyof typeof themes].background
        }}
      />
      
      {/* 底部命令输入区 */}
      <div 
        style={{ 
          padding: '12px 16px', 
          borderTop: '1px solid #f0f0f0',
          backgroundColor: '#fafafa',
          display: 'flex',
          gap: '8px',
          flexShrink: 0
        }}
      >
        <Input
          placeholder="Enter command..."
          value={command}
          onChange={(e) => setCommand(e.target.value)}
          onPressEnter={executeCommand}
          disabled={!connected}
          prefix={<span style={{ color: '#52c41a', fontFamily: 'monospace' }}>$</span>}
          style={{ fontFamily: 'monospace' }}
        />
        <Button 
          type="primary" 
          onClick={executeCommand}
          disabled={!connected || !command.trim()}
        >
          Run
        </Button>
      </div>
    </div>
  );
};

export default Terminal;
