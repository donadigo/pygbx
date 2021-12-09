# pygbx

A Python library to parse Gbx files, used in [TMTrackNN](https://github.com/donadigo/TMTrackNN) and other projects of mine that involve extracting
useful data from Gbx files.

# Examples

(For more documentation, refer to the docstrings in the source files.)

## Read metadata about a Challenge map:

```python
from pygbx import Gbx, GbxType

with Gbx('A01-Race.Challenge.Gbx') as g:
    challenge = g.get_class_by_id(GbxType.CHALLENGE)
    if not challenge:
        quit()

    print(f'Map Name: {challenge.map_name}')
    print(f'Map Author: {challenge.map_author}')
    print(f'Environment: {challenge.environment}')
```

### Output:

```
Map Name: A01-Race
Map Author: Nadeo
Environment: Stadium
```

## Enumerate blocks present in a Challenge map:

```python
from pygbx import Gbx, GbxType

with Gbx('A-0.Challenge.Gbx') as g:
    challenges = g.get_classes_by_ids([GbxType.CHALLENGE, GbxType.CHALLENGE_OLD])
    if not challenges:
        quit()

    challenge = challenges[0]
    for block in challenge.blocks:
        print(block)
```

### Output:

```
Name: StadiumRoadMainStartLine
Rotation: 0
Position: [16, 1, 13]
Flags: 0b1000000000000

Name: StadiumRoadMainGTDiag3x2Mirror
Rotation: 0
Position: [15, 1, 14]
Flags: 0b1000000000000

Name: StadiumRoadMainFinishLine
Rotation: 0
Position: [15, 1, 17]
Flags: 0b1000000000000

...
```

## Read metadata about a ghost in a Replay:

```python
from pygbx import Gbx, GbxType

with Gbx('A04_5_77.Replay.Gbx') as g:
    ghost = g.get_class_by_id(GbxType.CTN_GHOST)
    if not ghost:
        quit()

    print(f'Race time: {ghost.race_time}')
    print(f'Num respawns: {ghost.num_respawns}')
    print(f'Game version: {ghost.game_version}')
    print(f'Map UID: {ghost.uid}')
```

### Output:

```
Race time: 5770
Num respawns: 0
Game version: TmForever.2.11.26
Map UID: QQFcGaqYWgge5qyiErMR1KJgeuk
```
