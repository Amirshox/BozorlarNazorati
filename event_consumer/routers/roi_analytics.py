from fastapi import APIRouter, Depends, Security, status
from database import get_mongo_client
from datetime import datetime, timedelta

router = APIRouter(
    prefix='/roi_analytics',
    tags=['analytics']
)


#format of the date is 2021-09-01

today = datetime.now().strftime("%Y-%m-%d")
@router.get('/roi')
async def get_roi_analytics(roi_id: int, date=today, db=Depends(get_mongo_client)):
    roi_collections = db["roi"]

    single_date = datetime.fromisoformat(date)
    pipeline = [
        {
            '$match': {
                '@timestamp': {
                    '$gte': single_date,
                    '$lt': single_date + timedelta(days=1)  # End of the day
                },
                'roi_id': str(roi_id),
            }
        },
        {
            '$sort': {'@timestamp': 1}  # Sort by timestamp to calculate durations
        },
        {
            '$group': {
                '_id': '$roi_id',
                'events': {'$push': {'event_type': '$event_type', 'timestamp': '$@timestamp'}}
            }
        },
        {
            '$project': {
                'durations': {
                    '$map': {
                        'input': {'$range': [0, {'$subtract': [{'$size': '$events'}, 1]}]},
                        'as': 'idx',
                        'in': {
                            'start': {'$arrayElemAt': ['$events', '$$idx']},
                            'end': {'$arrayElemAt': ['$events', {'$add': ['$$idx', 1]}]}
                        }
                    }
                }
            }
        },
        {
            '$unwind': '$durations'
        },
        {
            '$project': {
                'event_type': '$durations.start.event_type',
                'duration': {
                    '$subtract': ['$durations.end.timestamp', '$durations.start.timestamp']
                }
            }
        },
        {
            '$group': {
                '_id': '$event_type',
                'totalDuration': {'$sum': '$duration'}
            }
        },
        {
            '$project': {
                '_id': 0,
                'eventType': '$_id',
                'totalDurationInMinutes': {'$divide': ['$totalDuration', 60000]}
                # Convert milliseconds to minutes
            }
        }
    ]

    result = list(roi_collections.aggregate(pipeline))
    return result


