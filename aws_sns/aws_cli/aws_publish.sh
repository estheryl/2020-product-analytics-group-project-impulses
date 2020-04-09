aws sns publish \
    --message $1 \
    --phone-number $2 \
    >> data/message_id.json