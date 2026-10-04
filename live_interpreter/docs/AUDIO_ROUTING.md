# Windows audio routing

## Recommended full-duplex setup

For reliable two-way translation, use **two independent virtual audio cables** (or an equivalent mixer with two virtual buses).

### Remote speaker -> you

```text
TrueConf/Telemost speaker output
  -> Virtual Cable A Input (playback endpoint)
  -> Virtual Cable A Output (recording endpoint)
  -> LiveInterpreter input: Cable A Output
  -> OpenAI translation -> Russian
  -> LiveInterpreter output: physical headphones
```

### You -> remote participant

```text
USB microphone
  -> LiveInterpreter input: USB microphone
  -> OpenAI translation -> target language
  -> LiveInterpreter output: Virtual Cable B Input
  -> TrueConf/Telemost microphone: Virtual Cable B Output
```

This separation prevents the Russian translated audio you hear from being re-captured and translated again.

## One-cable setup

One virtual cable is enough for **one-direction listen-along translation**. Full duplex with one cable is possible only with additional mixer/routing logic and is not recommended for the MVP because feedback loops are easy to create.

## Initial TrueConf / Telemost check

1. Route the meeting application's **speaker** to Cable A Input.
2. Route the meeting application's **microphone** to Cable B Output.
3. In LiveInterpreter:
   - Remote -> You input: Cable A Output.
   - Remote -> You output: your headphones.
   - You -> Remote input: USB microphone.
   - You -> Remote output: Cable B Input.
4. Use headphones, not speakers, during testing.
5. Start with only Remote -> You enabled. Confirm stable translation, then enable the reverse direction.
