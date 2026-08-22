class AchillesDetector:
    def detect(self, profile, data):
        return {
            "vulnerability": profile.core_wound,
            "trigger": profile.fear
        }
