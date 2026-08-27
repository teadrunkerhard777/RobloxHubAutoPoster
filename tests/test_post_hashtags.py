import unittest

from post_hashtags import add_post_hashtags, game_hashtag, hashtags_for_post


class PostHashtagTests(unittest.TestCase):
    def test_hits_use_automatic_game_hashtag(self):
        cases = {
            "Steal An Egg": "#Roblox #StealAnEgg #НовинкиRoblox",
            "Murder Mystery 2": "#Roblox #MurderMystery2 #НовинкиRoblox",
            "Animal Hospital (Anomaly)": ("#Roblox #AnimalHospital #НовинкиRoblox"),
            "+1 Speed Keyboard Escape": ("#Roblox #SpeedKeyboardEscape #НовинкиRoblox"),
        }

        for game, expected in cases.items():
            with self.subTest(game=game):
                text = add_post_hashtags(
                    "Текст выпуска",
                    "Новинки и хиты Roblox",
                    game,
                )
                self.assertEqual(text, f"Текст выпуска\n\n{expected}")
                self.assertEqual(
                    len(hashtags_for_post("Новинки и хиты Roblox", game)), 3
                )

    def test_game_hashtag_contains_only_latin_letters_and_numbers(self):
        self.assertEqual(game_hashtag("Murder Mystery 2"), "#MurderMystery2")
        self.assertEqual(game_hashtag("Animal Hospital (Anomaly)"), "#AnimalHospital")

    def test_useful_tips_use_three_rubric_tags(self):
        result = add_post_hashtags(
            "💡 ПОЛЕЗНО ЗНАТЬ\n\nСоветы",
            "Полезно знать",
            "Несколько игр",
        )
        self.assertTrue(result.endswith("#Roblox #ПолезноЗнать #RobloxHub"))
        self.assertEqual(len(hashtags_for_post("Полезно знать", "Несколько игр")), 3)

    def test_brawl_uses_three_brawl_tags(self):
        result = add_post_hashtags(
            "Совет Brawl Stars",
            "Brawl Stars: совет дня",
            "Brawl Stars",
        )
        self.assertEqual(
            result,
            "Совет Brawl Stars\n\n#BrawlStars #ПолезноЗнать #RobloxHub",
        )

    def test_image_without_text_uses_only_four_tags(self):
        result = add_post_hashtags(
            "",
            "Картинка дня",
            "Roblox",
            source="image_library",
        )
        self.assertEqual(
            result,
            "#Roblox #BrawlStars #StealABrainrot #99Nights",
        )
        self.assertEqual(len(result.split()), 4)

    def test_image_with_text_appends_tags_after_blank_line(self):
        result = add_post_hashtags(
            "Подпись к изображению",
            "Картинка дня",
            "Roblox",
            source="image_library",
        )
        self.assertEqual(
            result,
            "Подпись к изображению\n\n" "#Roblox #BrawlStars #StealABrainrot #99Nights",
        )

    def test_repeated_application_does_not_duplicate_tags(self):
        first = add_post_hashtags(
            "Текст",
            "Полезно знать",
            "Несколько игр",
        )
        second = add_post_hashtags(
            first,
            "Полезно знать",
            "Несколько игр",
        )
        self.assertEqual(second, first)


if __name__ == "__main__":
    unittest.main()
