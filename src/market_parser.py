import re
from datetime import datetime, timedelta

class MarketParser:
    def __init__(self):
        # Known cities for matching
        self.cities = ["london", "miami", "buenos-aires", "atlanta", "seoul", "seattle", "toronto", "chicago"]

    def parse_question(self, question, context=""):
        """
        Parses a Polymarket question with optional context (e.g. event title) to extract:
        - City
        - Strike Temperature
        - Direction (>=, <=)
        - Date
        - Unit (C or F)
        """
        combined = f"{context} {question}"
        lower_all = combined.lower()
        
        # 1. City extraction
        city = None
        for c in self.cities:
            clean_c = c.replace("-", " ")
            if clean_c in lower_all:
                city = c
                break
        
        # 2. Strike and Unit
        # Matches "75F", "75 F", "75°C", "75° C"
        strike_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:°?\s*([cf]))", combined, re.IGNORECASE)
        strike = None
        unit = "C" # Default
        if strike_match:
            strike = float(strike_match.group(1))
            unit = strike_match.group(2).upper()
        else:
            val_match = re.search(r"(\d+(?:\.\d+)?)", question)
            if val_match:
                strike = float(val_match.group(1))

        # 3. Direction
        direction = ">=" # Default
        if any(w in question.lower() for w in ["greater", "higher", "above", "more"]):
            direction = ">="
        elif any(w in question.lower() for w in ["less", "below", "lower"]):
            direction = "<="
            
        # 4. Date extraction
        # Handle "on February 7" or "on February 7, 2026"
        date_match = re.search(r"on ([A-Z][a-z]+ \d{1,2})(?:, (\d{4}))?", combined)
        target_date = None
        if date_match:
            try:
                date_text = date_match.group(1)
                year_text = date_match.group(2)
                year = int(year_text) if year_text else datetime.now().year
                dt = datetime.strptime(f"{date_text} {year}", "%B %d %Y")
                
                # Roll logic if year wasn't specified and date feels like past (same year)
                if not year_text and dt < datetime.now() - timedelta(days=5):
                    dt = dt.replace(year=year+1)
                
                target_date = dt.strftime("%Y-%m-%d")
            except:
                pass

        return {
            "city": city,
            "strike": strike,
            "direction": direction,
            "unit": unit,
            "date": target_date
        }
