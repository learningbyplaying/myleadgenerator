#
#
# ./run.sh muelles_com amisando provincias
# ./run.sh muelles_com amisando empresas
# ./run.sh muelles_com amisando website

#set -o allexport; source /app/.credentials; set +o allexport
export PYTHONIOENCODING=utf8
export PYTHONHASHSEED=0

CUSTOMER=$1
BASE=$2
ENTITY=$3

python3 /app/run.py "$CUSTOMER" "$BASE" "$ENTITY"