import os
import random
import json
import config

class QuestionManager:
    def __init__(self):
        self.questions = {
            'math': {},
            'english': {},
            'analytical': {}
        }
        self._load_questions()
    
    def _load_questions(self):
        print("Loading questions...")
        
        # Load math questions
        for topic in config.MATH_TOPICS:
            topic_path = os.path.join(config.IMAGE_PATHS['math'], topic)
            self.questions['math'][topic] = self._load_topic_questions(topic_path, topic)
            question_count = len(self.questions['math'][topic])
            if question_count > 0:
                print(f"Math/{topic}: {question_count} questions")
            else:
                print(f"Math/{topic}: No questions found")
        
        # Load english questions
        for topic in config.ENGLISH_TOPICS:
            topic_path = os.path.join(config.IMAGE_PATHS['english'], topic)
            self.questions['english'][topic] = self._load_topic_questions(topic_path, topic)
            question_count = len(self.questions['english'][topic])
            if question_count > 0:
                print(f"English/{topic}: {question_count} questions")
            else:
                print(f"English/{topic}: No questions found")
        
        # Load analytical questions
        for topic in config.ANALYTICAL_TOPICS:
            topic_path = os.path.join(config.IMAGE_PATHS['analytical'], topic)
            self.questions['analytical'][topic] = self._load_topic_questions(topic_path, topic)
            question_count = len(self.questions['analytical'][topic])
            if question_count > 0:
                print(f"Analytical/{topic}: {question_count} questions")
            else:
                print(f"Analytical/{topic}: No questions found")
    
    def _load_topic_questions(self, topic_path, topic_name):
        questions = []
        
        # Check if questions.json exists
        json_path = os.path.join(topic_path, 'questions.json')
        if os.path.exists(json_path):
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    questions = json.load(f)
                print(f"  ✓ Loaded from questions.json")
            except Exception as e:
                print(f"  ✗ Error loading {json_path}: {e}")
        
        # Load image files (but don't auto-create questions)
        # Images should be referenced in questions.json instead
        image_extensions = ['.png', '.jpg', '.jpeg', '.gif']
        if os.path.exists(topic_path):
            image_files = []
            for file in os.listdir(topic_path):
                if any(file.lower().endswith(ext) for ext in image_extensions):
                    image_files.append(file)
            
            if image_files:
                print(f"  📷 Found {len(image_files)} images")
        
        return questions
    
    def get_question(self, subject, topic):
        if subject not in self.questions or topic not in self.questions[subject]:
            return None
        
        questions = self.questions[subject][topic]
        if not questions:
            return None
        
        return random.choice(questions)
    
    def generate_mock_test(self):
        # This will be empty until you add questions
        return []