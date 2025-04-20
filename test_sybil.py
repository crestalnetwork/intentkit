from skills.sybil_checker.combined_checker import CombinedSybilChecker

config = {
    "api_key": "JJ3ZuaRt.myiyKaSSySNw74J1myDlU4M2KabnPlaa"
}

checker = CombinedSybilChecker(config)
result = checker.check_sybil("0x4c98bF5ADC39E12f81c214cC3A32Ef24F9CAbeB3")  # Replace with any wallet
print(result)
