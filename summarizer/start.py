#!/usr/bin/env python3
"""
文档总结服务启动脚本
"""

import os
import sys
import subprocess
from pathlib import Path

def check_dependencies():
    """检查依赖是否安装"""
    required_packages = {
        "fastapi": "fastapi",
        "uvicorn": "uvicorn",
        "httpx": "httpx",
        "anthropic": "anthropic",
    }

    missing_packages = []
    for display_name, import_name in required_packages.items():
        try:
            __import__(import_name)
        except ImportError:
            missing_packages.append(display_name)

    if missing_packages:
        print("缺少以下依赖包:")
        for package in missing_packages:
            print(f"   - {package}")
        print("\n请运行以下命令安装依赖:")
        print("pip install -r requirements.txt")
        return False

    print("所有依赖已安装")
    return True

def main():
    """主函数"""
    import argparse
    parser = argparse.ArgumentParser(description='文档总结服务')
    parser.add_argument('--host', default='0.0.0.0', help='主机地址')
    parser.add_argument('--port', type=int, default=8001, help='端口号')
    parser.add_argument('--reload', action='store_true', help='启用热重载')
    args = parser.parse_args()

    print("=" * 60)
    print("AI 文档总结服务")
    print("=" * 60)

    # 检查依赖
    if not check_dependencies():
        sys.exit(1)

    print(f"\n启动服务器...")
    print(f"后端 API: http://localhost:{args.port}")
    print(f"前端页面: 请在浏览器中打开 frontend/index.html")
    print(f"按 Ctrl+C 停止服务")
    print("=" * 60)

    # 切换到 backend 目录
    backend_dir = Path(__file__).parent / "backend"
    os.chdir(backend_dir)

    # 启动服务
    cmd = [
        sys.executable, "-m", "uvicorn", "main:app",
        "--host", args.host,
        "--port", str(args.port)
    ]

    if args.reload:
        cmd.append("--reload")

    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print("\n服务已停止")

if __name__ == "__main__":
    main()
