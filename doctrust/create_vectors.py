
model = None 

def main_model():
    global model
    if model is None:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("all-MiniLM-L6-v2")
    return model

# converting list of texts into vector embeddings
def embedded_texts(text_list):
    model = main_model()
    vectors = model.encode(text_list, convert_to_numpy=True)
    return vectors.tolist()

 # for embedding query 
def embedded_query(text):
    text_list = [text]
    result = embedded_texts(text_list)
    return result[0]
