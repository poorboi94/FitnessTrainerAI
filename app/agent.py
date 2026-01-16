import json
import os
from dotenv import load_dotenv
from groq import Groq
from typing import List, Dict, Any
from datetime import datetime

# TODO: Add error handling for rate limits
# TODO: Maybe cache common responses to save API calls?

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

class FitnessCoachAgent:
    """
    Main agent class for the fitness coach
    Uses a coordinator to route to different tools, then synthesizes the results
    """

    def __init__(self, user_data: Dict[str, Any], conversation_history: List[Dict] = None):
        self.user_data = user_data
        self.conversation_history = conversation_history or []

        # All the tools the agent can use
        self.tools = {
            "create_workout_plan": self.create_workout_plan,
            "create_meal_plan": self.create_meal_plan,
            "analyze_progress": self.analyze_progress,
            "give_motivation": self.give_motivation,
            "calculate_calories": self.calculate_calories,
            "injury_prevention": self.injury_prevention,
        }

    def _call_llm(self, messages: List[Dict], temperature: float = 0.7) -> str:
        """Basic wrapper around Groq API call"""
        try:
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=messages,
                temperature=temperature,
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"LLM call failed: {e}")
            raise

    def _get_conversation_context(self, last_n: int = 5) -> str:
        """Grab the last N messages for context"""
        if not self.conversation_history:
            return "No previous conversation."

        recent = self.conversation_history[-last_n:]
        context_lines = []
        for msg in recent:
            role = msg.get('role', 'unknown')
            # Truncate long messages so we don't blow up the prompt
            content = msg.get('content', '')[:100]
            context_lines.append(f"{role}: {content}")

        return "\n".join(context_lines)

    def _coordinator_llm(self, user_message: str) -> Dict:
        """
        This is the "brain" that decides which tools to use
        Returns a dict with tool names and reasoning
        """
        conversation_context = self._get_conversation_context(last_n=3)

        system_prompt = f"""You are a coordination system for a fitness coach.
            Look at what the user is asking and decide which tools to use.

            USER PROFILE:
            - Name: {self.user_data.get('username', 'User')}
            - Age: {self.user_data.get('age', 'unknown')}
            - Weight: {self.user_data.get('weight', 'unknown')} lb
            - Height: {self.user_data.get('height', 'unknown')} ft
            - Goal: {self.user_data.get('fitness_goal', 'not set')}
            - Activity Level: {self.user_data.get('activity_level', 'not set')}
            - Preferences: {self.user_data.get('preferences', 'none')}
            - Dietary Restrictions: {self.user_data.get('dietary_restrictions', 'none')}

            RECENT CONVERSATION:
            {conversation_context}

            AVAILABLE TOOLS:
            1. create_workout_plan - Creates personalized workout routines based on goals
            2. create_meal_plan - Creates personalized meal/nutrition plans
            3. analyze_progress - Analyzes fitness journey, identifies patterns and improvements
            4. give_motivation - Provides encouragement and motivational support
            5. calculate_calories - Calculates daily calorie needs and macros based on goals
            6. injury_prevention - Provides injury prevention advice and safe exercise guidance

            COORDINATION RULES:
            - Use context! If they asked about workouts before, consider that.
            - Can use MULTIPLE tools if needed (e.g., workout + motivation)
            - Use analyze_progress if they mention "progress", "doing", "results", "how am I"
            - Use motivation if they seem discouraged or ask for encouragement
            - For general questions, use NO tools (tools: [])

            Respond with ONLY valid JSON:
            {{
                "tools": ["tool_name1", "tool_name2"],
                "reasoning": "Brief explanation of why these tools",
                "context_aware": "How conversation history influenced this decision"
            }}
            """

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]

        # Using low temperature so we get consistent JSON back
        response = self._call_llm(messages, temperature=0.2)

        # Try to parse the JSON from the response
        # Sometimes the LLM adds extra text, so we need to extract just the JSON part
        try:
            start = response.find('{')
            end = response.rfind('}') + 1
            if start != -1 and end > start:
                json_str = response[start:end]
                return json.loads(json_str)
        except Exception as e:
            print(f"Coordination JSON parse error: {e}")

        # If parsing fails, just return empty tools
        return {"tools": [], "reasoning": "parsing error", "context_aware": "none"}

    def create_workout_plan(self, user_message: str) -> str:
        """
        Creates a workout plan
        Mines the conversation history to find what exercises they like/dislike
        """
        # Look through recent messages to see what they've mentioned
        likes = []
        dislikes = []

        for msg in self.conversation_history[-10:]:
            if msg.get('role') == 'user':
                content = msg.get('content', '').lower()

                # Check for dislikes FIRST (more specific)
                if "don't want" in content or "don't like" in content:
                    if 'lift' in content or 'weight' in content:
                        dislikes.append("weightlifting")
                    if 'run' in content:
                        dislikes.append("running")
                    if 'cardio' in content:
                        dislikes.append("cardio")
                    if 'gym' in content:
                        dislikes.append("gym workouts")
                # Check for likes (only if NOT in dislike context)
                elif 'like' in content or 'prefer' in content or 'want to' in content:
                    if 'run' in content or 'running' in content:
                        likes.append("running")
                    if 'lift' in content or 'weight' in content:
                        likes.append("weightlifting")
                    if 'cardio' in content:
                        likes.append("cardio")
                    if 'yoga' in content:
                        likes.append("yoga")
                    if 'swim' in content:
                        likes.append("swimming")

        likes_str = ", ".join(set(likes)) if likes else "none detected"
        dislikes_str = ", ".join(set(dislikes)) if dislikes else "none detected"

        system_prompt = f"""You are an expert fitness trainer creating personalized workout plans.
            USER PROFILE:
            - Age: {self.user_data.get('age', 'unknown')}
            - Weight: {self.user_data.get('weight', 'unknown')} lb
            - Height: {self.user_data.get('height', 'unknown')} ft
            - Goal: {self.user_data.get('fitness_goal', 'general fitness')}
            - Activity Level: {self.user_data.get('activity_level', 'moderate')}
            - Stated Preferences: {self.user_data.get('preferences', 'none')}

            CONVERSATION MEMORY:
            - User LIKES: {likes_str}
            - User DISLIKES: {dislikes_str}

            CRITICAL RULES:
            1. NEVER include exercises the user dislikes
            2. If they dislike weightlifting, use bodyweight exercises instead
            3. If they dislike running, use other cardio like cycling, rowing, or walking
            4. Prioritize activities they like
            5. Respect their preferences completely

            Create a detailed, personalized workout plan including:
            1. Workout name that reflects their goal
            2. Specific exercises with sets, reps, rest periods
            3. Duration (in minutes)
            4. Safety tips and modifications
            5. Why this plan matches their goal and preferences

            Format as a clear, structured plan."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]

        return self._call_llm(messages)

    def create_meal_plan(self, user_message: str) -> str:
        """Generate a meal plan based on their goals and restrictions"""
        system_prompt = f"""You are a nutritionist creating meal plans.
            USER PROFILE:
            - Age: {self.user_data.get('age', 'unknown')}
            - Weight: {self.user_data.get('weight', 'unknown')} lb
            - Goal: {self.user_data.get('fitness_goal', 'general fitness')}
            - Activity Level: {self.user_data.get('activity_level', 'moderate')}
            - Dietary Restrictions: {self.user_data.get('dietary_restrictions', 'none')}

            CRITICAL: Respect ALL dietary restrictions! If vegetarian, NO meat. If allergies, AVOID those foods.

            Create a detailed meal plan including:
            1. All meals: breakfast, lunch, dinner, snacks
            2. Calorie estimates per meal and total
            3. Macro breakdown (protein/carbs/fats in grams)
            4. Quick preparation tips
            5. Why this supports their fitness goal

            Be specific with portions and ingredients."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]

        return self._call_llm(messages)

    def analyze_progress(self, user_message: str) -> str:
        """
        Look through chat history to find patterns and improvements
        Counts workout mentions and detects positive or negative sentiment
        """
        progress_clues = []
        workout_mentions = 0

        # Search the whole conversation for workout-related stuff
        for msg in self.conversation_history:
            if msg.get('role') == 'user':
                content = msg.get('content', '').lower()
                if any(word in content for word in ['workout', 'exercise', 'ran', 'lifted', 'trained']):
                    workout_mentions += 1
                if 'tired' in content or 'sore' in content:
                    progress_clues.append("User mentioned physical fatigue (good sign of activity)")
                if 'easier' in content or 'better' in content:
                    progress_clues.append("User noted improvement")

        progress_summary = f"{workout_mentions} workout mentions; " + "; ".join(progress_clues[:3])

        system_prompt = f"""You are a fitness analyst providing insightful progress analysis.
            USER PROFILE:
            - Goal: {self.user_data.get('fitness_goal', 'general fitness')}
            - Activity Level: {self.user_data.get('activity_level', 'moderate')}
            - Started: {self.user_data.get('created_at', 'recently')}

            CONVERSATION ANALYSIS:
            {progress_summary}

            Total conversation messages: {len(self.conversation_history)}

            Provide a thoughtful analysis including:
            1. What progress indicators you see
            2. Positive patterns in their engagement
            3. Specific areas for improvement
            4. Actionable next steps
            5. Encouragement based on their actual activity

            Be honest but motivating. Use data from the conversation to be specific."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]

        return self._call_llm(messages)

    def give_motivation(self, user_message: str) -> str:
        """
        Motivation tool - tries to detect emotional tone and respond appropriately
        """
        # Grab recent user messages to check their mood
        recent_user_messages = [m.get('content', '') for m in self.conversation_history[-5:] if m.get('role') == 'user']
        emotional_context = "neutral"

        recent_text = " ".join(recent_user_messages).lower()
        # Simple sentiment detection
        if any(word in recent_text for word in ['tired', 'hard', 'difficult', 'struggle', 'cant']):
            emotional_context = "struggling, needs encouragement"
        elif any(word in recent_text for word in ['good', 'great', 'better', 'progress']):
            emotional_context = "positive, reinforce success"

        system_prompt = f"""You are a supportive fitness coach providing motivation.
            USER PROFILE:
            - Goal: {self.user_data.get('fitness_goal', 'general fitness')}
            - Activity Level: {self.user_data.get('activity_level', 'moderate')}

            EMOTIONAL CONTEXT: {emotional_context}

            Give them real motivation that:
            1. Acknowledges their specific goal
            2. Responds to how they're feeling
            3. Offers practical encouragement
            4. Gives them a specific next step

            Don't be generic! Make it personal."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]

        # Higher temperature for more varied responses
        return self._call_llm(messages, temperature=0.8)

    def calculate_calories(self, user_message: str) -> str:
        """
        Calorie calculator - uses Mifflin-St Jeor equation
        LLM does the actual math based on their profile data
        """
        weight_lb = self.user_data.get('weight', 0)
        height_ft = self.user_data.get('height', 0)
        age = self.user_data.get('age', 0)

        system_prompt = f"""You are a nutritionist calculating calorie needs.
            USER PROFILE:
            - Age: {age if age else 'unknown'}
            - Weight: {weight_lb} lb
            - Height: {height_ft} ft ({height_ft * 12:.1f} inches)
            - Gender: assumed male (adjust if needed)
            - Fitness Goal: {self.user_data.get('fitness_goal', 'not specified')}
            - Activity Level: {self.user_data.get('activity_level', 'moderate')}

            TASK: Calculate personalized daily calorie and macronutrient needs.

            CALCULATION STEPS:
            1. Calculate BMR using Mifflin-St Jeor:
                - Men: (10 * weight_kg) + (6.25 * height_cm) - (5 * age) + 5
                - Women: (10 * weight_kg) + (6.25 * height_cm) - (5 * age) - 161

            2. Calculate TDEE (BMR * activity multiplier):
                - Sedentary: 1.2
                - Light: 1.375
                - Moderate: 1.55
                - Active: 1.725
                - Very Active: 1.9

            3. Adjust for goal:
                - Lose weight: -500 cal (1 lb/week) or -250 cal (0.5 lb/week)
                - Gain muscle: +250-500 cal
                - Maintain: TDEE

            4. Calculate macros:
                - Protein: 0.8-1.2g per lb bodyweight (higher for muscle gain/fat loss)
                - Fats: 25-30% of total calories
                - Carbs: Remaining calories

            PROVIDE:
            1. BMR calculation with formula shown
            2. TDEE with activity multiplier
            3. Target daily calories for their goal
            4. Macro breakdown (grams and percentages)
            5. Meal timing suggestions
            6. Weekly expected progress (weight change)
            7. Tips for tracking and adjusting

            Show your work! Include the actual calculations so they understand."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]

        # Lower temperature for more accurate calculations
        return self._call_llm(messages, temperature=0.3)

    def injury_prevention(self, user_message: str) -> str:
        """
        Injury prevention tool
        Scans chat for exercise mentions and pain keywords
        """
        mentioned_exercises = []
        pain_indicators = []

        # Look through recent messages for exercise/pain mentions
        for msg in self.conversation_history[-10:]:
            if msg.get('role') == 'user':
                content = msg.get('content', '').lower()

                # Check for common exercises
                exercises = ['squat', 'deadlift', 'bench', 'run', 'lunge', 'press', 'curl', 'row']
                for exercise in exercises:
                    if exercise in content:
                        mentioned_exercises.append(exercise)

                # Check for pain/discomfort keywords
                pain_words = ['pain', 'hurt', 'sore', 'injury', 'strain', 'ache']
                for word in pain_words:
                    if word in content:
                        pain_indicators.append(f"mentioned '{word}'")

        exercise_context = ", ".join(set(mentioned_exercises)) if mentioned_exercises else "none mentioned yet"
        pain_context = "; ".join(set(pain_indicators)) if pain_indicators else "none reported"

        system_prompt = f"""You are a certified sports medicine specialist and injury prevention expert.

        USER PROFILE:
        - Age: {self.user_data.get('age', 'unknown')}
        - Weight: {self.user_data.get('weight', 'unknown')} lb
        - Fitness Goal: {self.user_data.get('fitness_goal', 'general fitness')}
        - Activity Level: {self.user_data.get('activity_level', 'moderate')}

        CONVERSATION CONTEXT:
        - Exercises mentioned: {exercise_context}
        - Pain indicators: {pain_context}

        CRITICAL: Provide practical, science-based injury prevention advice.

        PROVIDE:
        1. Specific risks for their goal/activity level
            - Age-related considerations
            - Common injuries for their activities

        2. Prevention strategies:
            - Warm-up protocols (specific exercises, duration)
            - Proper form tips for mentioned exercises
            - Progression guidelines (don't increase too fast)

        3. Recovery essentials:
            - Rest day recommendations
            - Sleep importance
            - Active recovery ideas

        4. Warning signs:
            - When to stop exercising
            - Difference between muscle soreness and injury
            - When to see a doctor

        5. Specific form cues:
            - If they mentioned exercises, give detailed form tips
            - Common mistakes to avoid

        Be specific and actionable. This could prevent a real injury!

        IMPORTANT DISCLAIMERS:
        - If they report pain, advise consulting a healthcare professional
        - Don't diagnose injuries - recommend professional evaluation
        - Emphasize proper progression over quick results"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]

        return self._call_llm(messages, temperature=0.5)

    def chat(self, user_message: str) -> str:
        """
        Main chat function - this is where the agentic magic happens
        1. Coordinator decides which tools to use
        2. Execute the tools
        3. Synthesize results into a natural response
        """
        # Step 1: Ask the coordinator what tools we need
        coordination = self._coordinator_llm(user_message)

        tools_to_use = coordination.get("tools", [])

        # Step 2: Run the tools
        tool_results = []
        for tool_name in tools_to_use:
            if tool_name in self.tools:
                try:
                    result = self.tools[tool_name](user_message)
                    tool_results.append({
                        "tool": tool_name,
                        "result": result
                    })
                except Exception as e:
                    # If a tool fails, record the error
                    tool_results.append({
                        "tool": tool_name,
                        "result": f"Error: {str(e)}"
                    })

        # Step 3: Synthesize the results
        if tool_results:
            tool_outputs = "\n\n".join([f"=== {tr['tool']} ===\n{tr['result']}" for tr in tool_results])

            # Combine all the tool outputs into one response
            synthesis_prompt = f"""You are a friendly fitness coach. Combine the info below into a natural response.
                USER: {self.user_data.get('username', 'User')}
                THEIR GOAL: {self.user_data.get('fitness_goal', 'general fitness')}

                They asked: "{user_message}"

                Tool outputs:
                {tool_outputs}

                Write a natural response that:
                1. Directly answers their question
                2. Uses the tool outputs but sounds human
                3. Feels personal, not robotic
                4. Ends with a question or next step

                Be warm and encouraging!"""

            messages = [{"role": "user", "content": synthesis_prompt}]
            final_response = self._call_llm(messages, temperature=0.7)

        else:
            # No tools needed, just have a conversation
            conversation_context = self._get_conversation_context(last_n=5)

            system_prompt = f"""You are a friendly fitness coach having a conversation.
                USER PROFILE:
                - Name: {self.user_data.get('username', 'User')}
                - Age: {self.user_data.get('age', 'unknown')}
                - Weight: {self.user_data.get('weight', 'unknown')} lb
                - Height: {self.user_data.get('height', 'unknown')} ft
                - Goal: {self.user_data.get('fitness_goal', 'not set yet')}
                - Activity Level: {self.user_data.get('activity_level', 'not set yet')}
                - Preferences: {self.user_data.get('preferences', 'none specified')}
                - Dietary Restrictions: {self.user_data.get('dietary_restrictions', 'none')}

                RECENT CONVERSATION:
                {conversation_context}

                Chat naturally! Remember what you've talked about before. If they ask for BMI or calories and you have their data, do the math for them."""

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ]
            final_response = self._call_llm(messages, temperature=0.7)

        return final_response
