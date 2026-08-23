FROM python:3.11-slim

WORKDIR /app
COPY raft_node.py /app/

# Default node config (overridden by env)
ENV NODE_ID=0 \
    PORT=6000 \
    PEERS=""

EXPOSE 6000

CMD python raft_node.py \
    --node-id ${NODE_ID} \
    --port ${PORT} \
    --peers ${PEERS} \
    $([ "$BYZANTINE" = "1" ] && echo --byzantine) \
    $([ "$AI_AUGMENTED" = "1" ] && echo --ai-augmented)
