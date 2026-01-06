#!/bin/bash

OUTPUT=~/Desktop/export.json
KEY="888fdc50-f53a-4cb4-b073-936e79c3bc07"

# 3关键词，每个关键词抓300条
KEYWORDS=("brevet" "commerce" "facture")
PER_KEY=300
PAGE_SIZE=50  # API每页最大数量，调整以便分页抓取

# 清空输出文件
echo "[" > "$OUTPUT"

COUNT=0

for QUERY in "${KEYWORDS[@]}"; do
    echo "Fetching keyword '$QUERY' ..."
    PAGE=0
    TOTAL_FETCHED=0

    while [ $TOTAL_FETCHED -lt $PER_KEY ]; do
        # 计算本页要抓的条数
        REMAIN=$((PER_KEY - TOTAL_FETCHED))
        PS=$PAGE_SIZE
        if [ $REMAIN -lt $PAGE_SIZE ]; then
            PS=$REMAIN
        fi

        # 请求当前页数据
        IDS=$(curl -s -H "accept: application/json" \
                 -H "KeyId: $KEY" \
            "https://sandbox-api.piste.gouv.fr/cassation/judilibre/v1.0/search?query=$QUERY&page=$PAGE&pageSize=$PS" \
            | jq -r '.results[] | select(.chamber=="comm") | .id')

        if [ -z "$IDS" ]; then
            echo "No more results for '$QUERY'"
            break
        fi

        # 循环抓取每个ID正文
        while IFS= read -r ID; do
            FULL=$(curl -s -H "accept: application/json" \
                         -H "KeyId: $KEY" \
                "https://sandbox-api.piste.gouv.fr/cassation/judilibre/v1.0/decision?id=$ID")
            
            COUNT=$((COUNT+1))
            TOTAL_FETCHED=$((TOTAL_FETCHED+1))

            # 添加到JSON数组
            if [ $COUNT -lt $((PER_KEY * ${#KEYWORDS[@]})) ]; then
                echo "$FULL," >> "$OUTPUT"
            else
                echo "$FULL" >> "$OUTPUT"
                break 2  # 达到900条就停止
            fi

            # 如果当前关键词已经抓够300条，跳出
            if [ $TOTAL_FETCHED -ge $PER_KEY ]; then
                break
            fi
        done <<< "$IDS"

        PAGE=$((PAGE+1))
    done
done

# 结束JSON数组
echo "]" >> "$OUTPUT"

echo "导出完成，共抓取 $COUNT 条商业法院判例，文件位置：$OUTPUT"

