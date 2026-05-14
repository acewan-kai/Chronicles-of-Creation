@echo off
chcp 65001 >nul
echo ========================================
echo  沉浸式AI小说创作平台 - 前端启动
echo ========================================
echo.

cd /d "%~dp0"

echo [1/2] 检查 Node.js...
where node >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未找到 Node.js，请先安装 Node.js 18+
    pause
    exit /b 1
)

echo [1/2] 检查依赖...
if not exist "node_modules" (
    echo [安装中] npm install...
    call npm install
    if %errorlevel% neq 0 (
        echo [错误] 依赖安装失败
        pause
        exit /b 1
    )
)

echo.
echo [2/2] 启动开发服务器...
echo.
echo 访问地址: http://localhost:3000
echo API地址: http://170.106.194.111:8000
echo.
echo 按 Ctrl+C 停止服务器
echo.

npm run dev

pause
