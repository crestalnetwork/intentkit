from .combined_checker import CombinedSybilChecker

def get_skills(config):
    return [CombinedSybilChecker(config)]
