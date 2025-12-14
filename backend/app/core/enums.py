from enum import Enum

class ReviewRating(str, Enum):
    again = "again"
    hard = "hard"
    good = "good"
    easy = "easy"
