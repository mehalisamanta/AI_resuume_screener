"""
Scoring and Similarity Calculation Utilities
"""

from config.settings import TFIDF_AVAILABLE

if TFIDF_AVAILABLE:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity

def calculate_semantic_score(resume_text, jd_text):
    """Calculate objective similarity score using TF-IDF"""
    if not TFIDF_AVAILABLE:
        return 0
    
    try:
        vectorizer = TfidfVectorizer(max_features=500, stop_words='english')
        vectors = vectorizer.fit_transform([resume_text, jd_text])
        score = cosine_similarity(vectors[0:1], vectors[1:2])[0][0]
        return round(score * 100, 2)
    except Exception as e:
        return 0