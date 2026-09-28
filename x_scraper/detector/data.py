"""Hand-labeled training data for the tweet detector.

Two tasks, both framed as text classification (not generation), because
that's what they actually are:

- Relevance: given (topic, tweet) -> is the tweet about that topic?
  Trained on (topic, text, label) triples spanning many topics so the
  model learns "does this text's vocabulary match this topic's vocabulary"
  rather than memorizing one fixed topic list.
- Sentiment: given tweet text -> positive / negative / neutral.

Deliberately includes the exact failure modes seen from the generic
instruction-following LLM: off-topic small talk that isn't secretly
"relevant to everything", and neutral/factual statements that aren't
secretly "positive".
"""

from __future__ import annotations

# (topic, text, is_relevant)
RELEVANCE_EXAMPLES: list[tuple[str, str, bool]] = [
    # AI
    ("AI", "Just shipped a new AI safety paper on interpretability.", True),
    ("AI", "New Claude model benchmarks look impressive for coding tasks.", True),
    ("AI", "GPT-4 hallucinated an entire fake API in my code review today.", True),
    ("AI", "Training a transformer from scratch on my laptop, send help.", True),
    ("AI", "Neural networks are just fancy curve fitting and I stand by that.", True),
    ("AI", "Lunch was great today, had a burger.", False),
    ("AI", "Watching the game tonight, go team!", False),
    ("AI", "My flight got delayed by three hours at JFK.", False),
    ("AI", "Just finished a 10k run, legs are destroyed.", False),
    ("AI", "New season of my favorite show drops Friday.", False),
    # sports
    ("sports", "That last-second three pointer was insane, what a game.", True),
    ("sports", "Injury report: starting QB is out for the season.", True),
    ("sports", "The transfer window is heating up, big names moving clubs.", True),
    ("sports", "Marathon training week 6, legs are sore but progress is real.", True),
    ("sports", "New AI safety paper on interpretability just dropped.", False),
    ("sports", "Fixed a nasty null pointer bug at work today.", False),
    ("sports", "Made pasta from scratch for the first time.", False),
    # crypto
    ("crypto", "Bitcoin broke $70k again, market's heating up.", True),
    ("crypto", "My wallet got drained by a phishing link, be careful out there.", True),
    ("crypto", "Ethereum gas fees are actually reasonable today for once.", True),
    ("crypto", "Just adopted a rescue dog, meet Biscuit.", False),
    ("crypto", "Coffee shop downtown has the best cold brew.", False),
    # food
    ("food", "This ramen recipe with a soft boiled egg is unreal.", True),
    ("food", "Tried a new taco truck, best al pastor in the city.", True),
    ("food", "Meal prepped chicken and rice for the whole week.", True),
    ("food", "Deployed a Kubernetes cluster for the first time, chaos.", False),
    ("food", "Stock market dipped 2% on inflation fears.", False),
    # politics
    ("politics", "New bill passed the senate after a tense floor vote.", True),
    ("politics", "Election turnout numbers just released for the primary.", True),
    ("politics", "Debate over the budget bill got heated in committee today.", True),
    ("politics", "My cat knocked a plant off the balcony again.", False),
    ("politics", "Finally beat the final boss after 40 attempts.", False),
    # gaming
    ("gaming", "New patch nerfs the meta build everyone was abusing.", True),
    ("gaming", "Speedran the whole game in under two hours, new PB.", True),
    ("gaming", "Servers are down again for the third time this week.", True),
    ("gaming", "Signed the lease on a new apartment today.", False),
    ("gaming", "Weather's been brutal this week, 100+ every day.", False),
    # climate
    ("climate", "Record heat wave hitting the Pacific Northwest this week.", True),
    ("climate", "New report shows emissions dropped in the EU this quarter.", True),
    ("climate", "Solar panel install finally finished, producing more than we use.", True),
    ("climate", "Just got back from a great concert downtown.", False),
    ("climate", "Refactored the whole auth module, feels so much cleaner now.", False),
    # music
    ("music", "New album dropped at midnight and it's already on repeat.", True),
    ("music", "Front row tickets for the reunion tour, still shaking.", True),
    ("music", "Learning guitar again after a ten year break.", True),
    ("music", "Passed my driving test on the second try.", False),
    ("music", "Quarterly earnings beat expectations across the board.", False),
]

# (text, label) — label in {"positive", "negative", "neutral"}
SENTIMENT_EXAMPLES: list[tuple[str, str]] = [
    # positive
    ("Just shipped a feature I'm really proud of, team crushed it.", "positive"),
    ("Best meal I've had all year, absolutely incredible.", "positive"),
    ("So grateful for everyone who showed up today, means a lot.", "positive"),
    ("We won! Can't stop smiling right now.", "positive"),
    ("This new album is a masterpiece front to back.", "positive"),
    ("Finally hit my savings goal, feels amazing.", "positive"),
    ("Congrats to the whole team on the launch, well deserved.", "positive"),
    ("Woke up early and had the most peaceful morning walk.", "positive"),
    # negative
    ("This outage has been going on for six hours, completely unacceptable.", "negative"),
    ("Worst customer service I've ever dealt with, never again.", "negative"),
    ("Lost my luggage and the airline won't even respond.", "negative"),
    ("Heartbroken about the news today, this is devastating.", "negative"),
    ("Absolutely furious, they cancelled the event with zero notice.", "negative"),
    ("My code broke production again, I hate everything right now.", "negative"),
    ("This traffic is making me miss my flight, awful start to the day.", "negative"),
    ("Disappointed in how that meeting went, nothing got resolved.", "negative"),
    # neutral
    ("Lunch was great today, had a burger.", "neutral"),
    ("Meeting moved to 3pm, updated the calendar invite.", "neutral"),
    ("New Claude model benchmarks look impressive for coding tasks.", "neutral"),
    ("Bitcoin broke $70k again, market's heating up.", "neutral"),
    ("Flight lands at 6:45, texting you when I'm off the plane.", "neutral"),
    ("New patch nerfs the meta build everyone was abusing.", "neutral"),
    ("Reading through the Q3 report before the call tomorrow.", "neutral"),
    ("Grabbing groceries after work, need anything?", "neutral"),
    ("Election turnout numbers just released for the primary.", "neutral"),
    ("Server maintenance scheduled for Sunday 2-4am UTC.", "neutral"),
]
