#set -o allexport; source /app/.credentials; set +o allexport
export PYTHONIOENCODING=utf8
export PYTHONHASHSEED=0

PROJECT_PATH=$1

python3 /app/run.py "$PROJECT_PATH"