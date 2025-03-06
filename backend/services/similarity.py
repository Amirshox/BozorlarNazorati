import os

from elasticsearch import Elasticsearch
from sqlalchemy.orm import Session

from models import Identity

ELASTIC_SEARCH_URL = os.environ.get("ELASTIC_SEARCH_URL")

try:
    elastic_client = Elasticsearch(ELASTIC_SEARCH_URL, verify_certs=False)
except Exception as e:
    print(f"Error connecting to ElasticSearch, {e}")


def get_attendance_similarity_in_area(attendance):
    radius = 20_000  # 20km
    if attendance.embedding512 is None:
        return []
    embedding512 = eval(attendance.embedding512)[0]

    try:
        res = elastic_client.search(
            index="similarity_attendance_photo",
            body={
                "query": {
                    "script_score": {
                        "query": {
                            "bool": {
                                "filter": {
                                    "geo_distance": {
                                        "distance": f"{radius}m",
                                        "location": {"lat": attendance.lat, "lon": attendance.lon},
                                    }
                                },
                                "must_not": {"match": {"_id": attendance.identity_id}},
                            }
                        },
                        "script": {
                            "source": "1 / (1 + l2norm(params.queryVector, 'embedding'))",  # Euclidean distance
                            "params": {"queryVector": embedding512},
                        },
                    }
                },
                "min_score": 0.5,
            },
        )
    except Exception as e:
        print(f"Error: {e}")
        res = {"hits": {"hits": []}}

    hits = res["hits"]["hits"]
    similar = []
    for hit in hits:
        hit["_source"].pop("embedding")
        hit["_source"]["distance"] = 1 - hit["_score"]
        similar.append(hit["_source"])
    response = similar
    return response


def get_attendance_similarity_in_entity(attendance):
    radius = 20_000  # 20km
    if attendance.embedding512 is None:
        return []
    embedding512 = eval(attendance.embedding512)[0]

    try:
        res = elastic_client.search(
            index="similarity_attendance_photo_in_entity",
            body={
                "query": {
                    "script_score": {
                        "query": {
                            "bool": {
                                "filter": {
                                    "geo_distance": {
                                        "distance": f"{radius}m",
                                        "location": {"lat": attendance.lat, "lon": attendance.lon},
                                    }
                                },
                                "must_not": {"match": {"_id": attendance.identity_id}},
                                "must": {"match": {"tenant_entity_id": attendance.tenant_entity_id}},
                            }
                        },
                        "script": {
                            "source": "1 / (1 + l2norm(params.queryVector, 'embedding'))",  # Euclidean distance
                            "params": {"queryVector": embedding512},
                        },
                    }
                },
                "min_score": 0.5,
            },
        )
    except Exception as e:
        print(f"Error: {e}")
        res = {"hits": {"hits": []}}

    hits = res["hits"]["hits"]
    similar = []
    for hit in hits:
        hit["_source"].pop("embedding")
        hit["_source"]["distance"] = 1 - hit["_score"]
        similar.append(hit["_source"])
    response = similar
    return response


def get_main_photo_similarity(db: Session, identity_id: int, lat: float, lon: float):
    radius = 20_000  # 20km

    identity = db.query(Identity).filter_by(id=identity_id, is_active=True).first()
    if not identity:
        return []
    if identity.embedding512 is None:
        return []
    embedding512 = eval(identity.embedding512)[0]

    try:
        res = elastic_client.search(
            index="similarity_main_photo",
            body={
                "query": {
                    "script_score": {
                        "query": {
                            "bool": {
                                "filter": {
                                    "geo_distance": {"distance": f"{radius}m", "location": {"lat": lat, "lon": lon}}
                                },
                                "must_not": {"match": {"_id": identity_id}},
                            }
                        },
                        "script": {
                            "source": "1 / (1 + l2norm(params.queryVector, 'embedding'))",  # Euclidean distance
                            "params": {"queryVector": embedding512},
                        },
                    }
                },
                "min_score": 0.5,
            },
        )
    except Exception as e:
        print(f"Error: {e}")
        res = {"hits": {"hits": []}}

    hits = res["hits"]["hits"]
    similar = []
    for hit in hits:
        hit["_source"].pop("embedding")
        hit["_source"]["distance"] = 1 - hit["_score"]
        similar.append(hit["_source"])
    response = similar
    return response
