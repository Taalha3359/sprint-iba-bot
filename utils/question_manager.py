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
    
    def _load_topic_questions(self, topic_path, subject, topic_name):
    questions = []
    
    # Check if questions.json exists
    json_path = os.path.join(topic_path, 'questions.json')
    if os.path.exists(json_path):
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                questions = json.load(f)
            
            # FIX IMAGE PATHS - This is the key fix!
            for question in questions:
                if 'image_path' in question:
                    image_rel_path = question['image_path']
                    
                    # If path is relative, make it absolute relative to the topic folder
                    if not os.path.isabs(image_rel_path):
                        # Join with the topic path to get full absolute path
                        absolute_path = os.path.join(topic_path, image_rel_path)
                        question['image_path'] = absolute_path
                    
                    # Verify the image actually exists
                    if not os.path.exists(question['image_path']):
                        print(f"❌ Image not found: {question['image_path']}")
                        # Remove invalid path to prevent errors
                        question.pop('image_path', None)
                    else:
                        print(f"✅ Image found: {question['image_path']}")
                        
        except Exception as e:
            print(f"Error loading {json_path}: {e}")
    
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
