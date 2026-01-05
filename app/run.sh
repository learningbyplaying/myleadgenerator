#set -o allexport; source /app/.credentials; set +o allexport
export PYTHONIOENCODING=utf8
export PYTHONHASHSEED=0

CUSTOMER=$1
ENTITY=$2

python3 /app/run.py "$CUSTOMER" "$ENTITY"