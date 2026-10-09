"""Auswahl-Hilfe (Entdecken / 'Waehlt aus'): Log-Parsing und Bewertung der Optionen."""
import unittest

from hscoach import choices
from hscoach.state import Choice, ChoiceOption

from tests.helpers import gs, mm, new_tracker

P = "D 23:51:20.1234567 GameState.{} - "
HEAD = P.format("DebugPrintEntityChoices()")
CHOSEN = P.format("DebugPrintEntitiesChosen()")


def choice_lines(player="undelete", ctype="GENERAL"):
    return [
        HEAD + f"id=3 Player={player} TaskList=425 ChoiceType={ctype} CountMin=1 CountMax=1",
        HEAD + "  Source=[entityName=Arkane Schlüsselmacherin id=82 zone=PLAY zonePos=2 cardId=Story_01_ArcaneKeysmith player=1]",
        HEAD + "  Entities[0]=[entityName=Zerstäuben id=174 zone=SETASIDE zonePos=0 cardId=EX1_594 player=1]",
        HEAD + "  Entities[1]=[entityName=Eisbarriere id=175 zone=SETASIDE zonePos=0 cardId=EX1_289 player=1]",
        HEAD + "  Entities[2]=[entityName=Spiegelgestalt id=176 zone=SETASIDE zonePos=0 cardId=EX1_294 player=1]",
    ]


class TestParse(unittest.TestCase):
    def test_choice_is_recorded(self):
        tr = new_tracker()
        tr.feed_lines(choice_lines())
        ch = tr.choice
        self.assertEqual([o["cid"] for o in ch["options"]], ["EX1_594", "EX1_289", "EX1_294"])
        self.assertEqual(ch["source"]["name"], "Arkane Schlüsselmacherin")

    def test_choice_cleared_when_chosen(self):
        tr = new_tracker()
        tr.feed_lines(choice_lines() + [CHOSEN + "id=3 Player=undelete EntitiesCount=1"])
        self.assertIsNone(tr.choice)

    def test_other_id_does_not_clear(self):
        tr = new_tracker()
        tr.feed_lines(choice_lines() + [CHOSEN + "id=7 Player=undelete EntitiesCount=1"])
        self.assertIsNotNone(tr.choice)

    def test_mulligan_ignored(self):
        tr = new_tracker()
        tr.feed_lines(choice_lines(ctype="MULLIGAN"))
        self.assertIsNone(tr.choice)


SECRETS = [
    ChoiceOption(174, "EX1_594", "Zerstäuben", "SPELL", 3, text="Geheimnis: Wenn ein Diener Euren Helden angreift, vernichtet ihn.", secret=True),
    ChoiceOption(175, "EX1_289", "Eisbarriere", "SPELL", 3, text="Geheimnis: Wenn Euer Held angegriffen wird, erhält er 8 Rüstung.", secret=True),
    ChoiceOption(176, "EX1_294", "Spiegelgestalt", "SPELL", 3,
                 text="Geheimnis: Wenn Euer Gegner einen Diener ausspielt, ruft eine Kopie davon herbei.", secret=True),
]


class TestAdvise(unittest.TestCase):
    def test_mirror_entity_wins_when_my_board_blocks(self):
        s = gs(my_hp=24, mine=[mm(1, "Kalec", 4, 4), mm(2, "Schlüsselmacherin", 2, 2)],
               opp=[mm(10, "Kurierin", 6, 2), mm(11, "Kampfmagierin", 3, 2)], opp_hand_count=4)
        ranked = choices.advise(Choice(3, "Schlüsselmacherin", SECRETS), s)
        self.assertEqual(ranked[0].name, "Spiegelgestalt")
        self.assertEqual(len(ranked), 3)

    def test_vaporize_wins_with_empty_board_and_many_attackers(self):
        s = gs(my_hp=20, opp=[mm(10, "A", 5, 5), mm(11, "B", 4, 4), mm(12, "C", 3, 3)], opp_hand_count=0)
        ranked = choices.advise(Choice(3, "x", SECRETS), s)
        self.assertEqual(ranked[0].name, "Zerstäuben")

    def test_mirror_entity_is_weak_without_opponent_cards(self):
        s = gs(opp=[mm(10, "A", 5, 5)], opp_hand_count=0)
        ranked = choices.advise(Choice(3, "x", SECRETS), s)
        self.assertNotEqual(ranked[0].name, "Spiegelgestalt")

    def test_taunt_minion_preferred_when_low(self):
        opts = [ChoiceOption(1, "A", "Riese", "MINION", 5, atk=5, hp=5, text=""),
                ChoiceOption(2, "B", "Wächter", "MINION", 5, atk=3, hp=6, text="Spott")]
        s = gs(my_hp=8, opp=[mm(10, "A", 5, 5), mm(11, "B", 4, 4)])
        self.assertEqual(choices.advise(Choice(1, "x", opts), s)[0].name, "Wächter")

    def test_render_marks_best(self):
        s = gs(opp=[mm(10, "A", 5, 5)], opp_hand_count=3)
        text, ranked = choices.render(Choice(3, "Schlüsselmacherin", SECRETS), s)
        self.assertIn("★ " + ranked[0].name, text)
        self.assertTrue(text.startswith("AUSWAHL OFFEN"))


if __name__ == "__main__":
    unittest.main()
