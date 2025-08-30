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
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        print(f"Base directory: {self.base_dir}")
        self._load_questions()
        self._print_question_stats()
    
    def _print_question_stats(self):
        print("\n=== QUESTION LOADING STATISTICS ===")
        total_questions = 0
        for subject, topics in self.questions.items():
            print(f"\n{subject.upper()}:")
            for topic, questions in topics.items():
                print(f"  {topic}: {len(questions)} questions")
                total_questions += len(questions)
        print(f"\nTOTAL QUESTIONS LOADED: {total_questions}")
    
    def _load_questions(self):
        print("Loading questions...")
        
        # Load math questions
        for topic in config.MATH_TOPICS:
            topic_path = os.path.join(self.base_dir, 'images', 'math', topic)
            self.questions['math'][topic] = self._load_topic_questions(topic_path, 'math', topic)
            question_count = len(self.questions['math'][topic])
            if question_count > 0:
                print(f"Math/{topic}: {question_count} questions")
            else:
                print(f"Math/{topic}: No questions found")
        
        # Load english questions
        for topic in config.ENGLISH_TOPICS:
            topic_path = os.path.join(self.base_dir, 'images', 'english', topic)
            self.questions['english'][topic] = self._load_topic_questions(topic_path, 'english', topic)
            question_count = len(self.questions['english'][topic])
            if question_count > 0:
                print(f"English/{topic}: {question_count} questions")
            else:
                print(f"English/{topic}: No questions found")
        
        # Load analytical questions
        for topic in config.ANALYTICAL_TOPICS:
            topic_path = os.path.join(self.base_dir, 'images', 'analytical', topic)
            self.questions['analytical'][topic] = self._load_topic_questions(topic_path, 'analytical', topic)
            question_count = len(self.questions['analytical'][topic])
            if question_count > 0:
                print(f"Analytical/{topic}: {question_count} questions")
            else:
                print(f"Analytical/{topic}: No questions found")
    
    def _load_topic_questions(self, topic_path, subject, topic_name):
        questions = []
        
        # Check if questions.json exists for this topic
        json_path = os.path.join(topic_path, 'questions.json')
        if os.path.exists(json_path):
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    file_content = f.read().strip()
                    
                    # Check if file is empty
                    if not file_content:
                        print(f"WARNING: Empty questions.json at {json_path}")
                        return questions
                    
                    # Try to parse JSON
                    questions = json.loads(file_content)
                    
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
                    
                    print(f"✓ Loaded {len(questions)} questions from {json_path}")
                    
            except json.JSONDecodeError as e:
                print(f"ERROR: Invalid JSON in {json_path}")
                print(f"JSON Error: {e}")
            except Exception as e:
                print(f"ERROR loading questions from {json_path}: {e}")
        else:
            print(f"WARNING: questions.json not found at {json_path}")
        
        # Also load image files if no questions were loaded from JSON
        if not questions:
            questions = self._load_images_as_questions(topic_path)
        
        return questions
    
    def _load_images_as_questions(self, topic_path):
        questions = []
        image_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.webp']
        
        if os.path.exists(topic_path):
            try:
                image_files = []
                for file in os.listdir(topic_path):
                    if any(file.lower().endswith(ext) for ext in image_extensions):
                        image_files.append(file)
                
                for image_file in image_files:
                    # Create a question entry for the image
                    image_path = os.path.join(topic_path, image_file)
                    questions.append({
                        'question': f"Refer to the image for this problem",
                        'options': ['A', 'B', 'C', 'D', 'E'],
                        'correct_answer': 0,
                        'image_path': image_path
                    })
                
                if questions:
                    print(f"✓ Created {len(questions)} questions from images in {topic_path}")
                    
            except Exception as e:
                print(f"ERROR loading images from {topic_path}: {e}")
        
        return questions
    
    def get_question(self, subject, topic):
        if subject not in self.questions:
            print(f"ERROR: Subject '{subject}' not found")
            return None
        
        if topic not in self.questions[subject]:
            print(f"ERROR: Topic '{topic}' not found in subject '{subject}'")
            return None
        
        questions = self.questions[subject][topic]
        if not questions:
            print(f"WARNING: No questions available for {subject}/{topic}")
            return None
        
        # Select a random question
        selected_question = random.choice(questions)
        
        # Verify the image exists if specified
        if 'image_path' in selected_question:
            image_path = selected_question['image_path']
            if not os.path.exists(image_path):
                print(f"WARNING: Image file not found: {image_path}")
                # Remove the invalid image path
                selected_question = selected_question.copy()
                selected_question.pop('image_path', None)
        
        return selected_question
    
    def generate_mock_test(self):
        test_questions = []
        
        # Add math questions
        math_count = config.MOCK_TEST_CONFIG['math_count']
        math_questions = []
        for topic, questions in self.questions['math'].items():
            math_questions.extend(questions)
        
        if math_questions:
            test_questions.extend(random.sample(math_questions, min(math_count, len(math_questions))))
        
        # Add english questions
        english_count = config.MOCK_TEST_CONFIG['english_count']
        english_questions = []
        for topic, questions in self.questions['english'].items():
            english_questions.extend(questions)
        
        if english_questions:
            test_questions.extend(random.sample(english_questions, min(english_count, len(english_questions))))
        
        # Add analytical questions
        analytical_count = config.MOCK_TEST_CONFIG['analytical_count']
        analytical_questions = []
        for topic, questions in self.questions['analytical'].items():
            analytical_questions.extend(questions)
        
        if analytical_questions:
            test_questions.extend(random.sample(analytical_questions, min(analytical_count, len(analytical_questions))))
        
        # Shuffle questions
        random.shuffle(test_questions)
        
        return test_questions
