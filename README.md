# 提交代码
git pull --rebase origin main   
git add .
git commit -m "xxx"
git push origin main

# 1. 开始工作前
cd CardMigrator-System
conda activate cardmig

# 2. 启动 Jupyter 写笔记本
jupyter notebook

# 3. 或者启动 Flask 后端
python local/app.py

# 4. 或者启动前端调试服务器
npx http-server . -p 8080

# 5. 工作结束
conda deactivate

# 安装新包
# 1. 安装新包（例如安装 pandas）
conda install pandas

# 2. 立即更新 environment.yml
conda env export > environment.yml

# 换电脑时的恢复流程
# 1. 克隆项目
git clone https://github.com/yourname/CardMigrator-System.git
cd CardMigrator-System

# 2. 用 environment.yml 重建完全一样的环境
conda env create -f environment.yml

# 3. 激活环境
conda activate cardmig

# 4. 环境就绪，可以开始工作了