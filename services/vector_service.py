import os
import pandas as pd
from qdrant_client import QdrantClient
from qdrant_client.http import models
from services.embedding_service import embedding_service

COLLECTION_NAME = "estateiq_properties"

class VectorService:
    def __init__(self):
        qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
        self.client = QdrantClient(url=qdrant_url)

    def init_collection(self, csv_path: str = "data/properties.csv"):
        try:
            collections = [c.name for c in self.client.get_collections().collections]
            if COLLECTION_NAME not in collections:
                self.client.create_collection(
                    collection_name=COLLECTION_NAME,
                    vectors_config=models.VectorParams(
                        size=384, 
                        distance=models.Distance.COSINE
                    )
                )
                self.index_properties_from_csv(csv_path)
        except Exception as e:
            print(f"[Qdrant Warning] Failed to initialize collection: {e}")

    def create_text_representation(self, row: pd.Series) -> str:
        return (
            f"{row['bedrooms']}BHK {row['property_type']} in {row['city']} {row['locality']}. "
            f"Price {row['price']} INR. {row['area_sqft']} sqft. {row['furnishing']}. "
            f"Parking: {row['parking']}. Near metro: {row['nearby_metro']} "
            f"({row['metro_distance_km']} km away). Description: {row['description']}. "
            f"Amenities: {row['amenities']}."
        )

    def index_properties_from_csv(self, csv_path: str):
        if not os.path.exists(csv_path):
            return
        df = pd.read_csv(csv_path)
        points = []
        for idx, row in df.iterrows():
            text = self.create_text_representation(row)
            vector = embedding_service.generate_embedding(text)
            payload = row.to_dict()
            points.append(
                models.PointStruct(
                    id=int(row["property_id"]),
                    vector=vector,
                    payload=payload
                )
            )
        self.client.upsert(collection_name=COLLECTION_NAME, points=points)

    def search_properties(self, query: str, limit: int = 5, filters: dict = None) -> list[dict]:
        try:
            query_vector = embedding_service.generate_embedding(query)
            qdrant_filters = []
            
            if filters:
                if "max_price" in filters and filters["max_price"]:
                    qdrant_filters.append(
                        models.FieldCondition(
                            key="price",
                            range=models.Range(lte=float(filters["max_price"]))
                        )
                    )
                if "bedrooms" in filters and filters["bedrooms"]:
                    qdrant_filters.append(
                        models.FieldCondition(
                            key="bedrooms",
                            match=models.MatchValue(value=int(filters["bedrooms"]))
                        )
                    )

            query_filter = models.Filter(must=qdrant_filters) if qdrant_filters else None

            # Replaced self.client.search with self.client.query_points
            response = self.client.query_points(
                collection_name=COLLECTION_NAME,
                query=query_vector,
                query_filter=query_filter,
                limit=limit
            )
            
            out = []
            for res in response.points:
                data = res.payload
                data["similarity_score"] = round(float(res.score), 4)
                out.append(data)
            return out
        except Exception as e:
            print(f"[Vector Search Error]: {e}")
            return []

    def get_similar_properties(self, property_id: int, limit: int = 4) -> list[dict]:
        try:
            records = self.client.retrieve(
                collection_name=COLLECTION_NAME,
                ids=[property_id],
                with_vectors=True
            )
            if not records:
                return []
            target_vector = records[0].vector

            # Replaced self.client.search with self.client.query_points
            response = self.client.query_points(
                collection_name=COLLECTION_NAME,
                query=target_vector,
                query_filter=models.Filter(
                    must_not=[
                        models.FieldCondition(
                            key="property_id",
                            match=models.MatchValue(value=property_id)
                        )
                    ]
                ),
                limit=limit
            )
            out = []
            for res in response.points:
                data = res.payload
                data["similarity_score"] = round(float(res.score), 4)
                out.append(data)
            return out
        except Exception as e:
            print(f"[Similar Search Error]: {e}")
            return []

vector_service = VectorService()