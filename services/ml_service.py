# import pickle
# from sklearn.metrics.pairwise import cosine_similarity

# tfidf = pickle.load(open("model/tfidf.pkl", "rb"))

# def evaluate_resume(job_text, resume_text):

#     job_text = job_text.lower()
#     resume_text = resume_text.lower()

#     job_vector = tfidf.transform([job_text])
#     resume_vector = tfidf.transform([resume_text])

#     score = cosine_similarity(job_vector, resume_vector)[0][0]

#     return round(score * 100, 2)


import pickle
import re
from sklearn.metrics.pairwise import cosine_similarity

tfidf = pickle.load(open("model/tfidf.pkl", "rb"))

def extract_keywords(text):
    words = re.findall(r'\b[a-zA-Z]+\b', text.lower())
    return set(words)

def evaluate_resume(job_text, resume_text):

    job_text = job_text.lower()
    resume_text = resume_text.lower()

    job_vector = tfidf.transform([job_text])
    resume_vector = tfidf.transform([resume_text])

    score = cosine_similarity(job_vector, resume_vector)[0][0]
    score_percentage = round(score * 100, 2)

    # 🔥 Skill Matching
    job_keywords = extract_keywords(job_text)
    resume_keywords = extract_keywords(resume_text)

    matched = job_keywords.intersection(resume_keywords)
    missing = job_keywords - resume_keywords

    return {
        "score": score_percentage,
        "matched_skills": list(matched)[:15],
        "missing_skills": list(missing)[:15]
    }