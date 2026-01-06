
FILE_INPUT=$1

## Get Email unicos
#csvcut -c email /data/muelles_com/amisando/website.csv | sort | uniq -c

## Count
echo "Count total"
wc -l $FILE_INPUT

## Count
echo "Count Email unicos"
csvcut -c email /data/muelles_com/amisando/website.csv | sort | uniq -c | wc -l 
