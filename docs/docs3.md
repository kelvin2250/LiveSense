# làm việc với DB 

- vào docker : docker exec -it postgres psql -U phat -d metabaseappdb
        - \d : xem schema
        - \d table_name : xem table
        - \l : xem database
        - \c database_name : chuyen database
        - \dt : xem table
        - \d+ table_name : xem table chi tiết
        - \q : thoat
### eda 
        select * from chat_history_analysis limit 5;
        select * from stream_signals_history limit 5;
        select count(*) from chat_history_analysis;
        select count(*) from stream_signals_history;

table : chat_history_analysis , stream_signals_history
- docker exec -it spark-master bash

# run producer : python producer2.py --video_id VIDEO_ID (8Buyp1C860A) --topic topic_name (live_chat_himas)
# run consumer : docker exec -it spark-master /opt/spark/bin/spark-submit `
  --master spark://spark-master:7077 `
  --conf spark.jars.ivy=/tmp/.ivy `
  --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0,org.postgresql:postgresql:42.6.0 `
  /app/consumer.py  --topic live_chat_rambo 
 python producer.py --video_id MGV5PJuhgvc --topic live_chat_rambo

 python producer2.py --video_id  8Buyp1C860A --topic  live_chat_himas