# PINEAL-HERETIC v2.0 / v3.0

**PINEAL-HERETIC**, hedef sosyal medya profillerini (Instagram / X) anonim olarak tarayan, psikolojik analiz (AÅŸil Tendonu, Temel Yara, KaranlÄ²k Detay, Frekans RezonansÄ±) gerÃ§ekleÅŸtiren ve otonom iletiÅŸim stratejileri Ã¼reten bir yapay zeka analiz platformudur.

---

## 1. GerÃ§ek Sistem Mimarisi

```JSON
Svelte UI (Port 5173)  â”€â”€[HTTP / WebSecket]â”€â”€>  FastAPI (Port 8000)
                                                              â”‚
                                                              â–¼
                                                          PinealExecutor
                                                             â”‚
                       â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â•±Â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
                       â–¼                                       â–¼                                      â–¼
                 MirrorOfTruth               AutonomousVerifier             HumanBehaviorAnalyzer
                        â”€                              â”€                              â”€
                        â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â•±Â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
                                                              â”‚
                                                              â–¼
                                                        ResonanceCalculator
                                                             â”‚
                                                              â–¼
                                                          PatternInterrupt
                                                              â”‚
                                                              â–¼
                                                          LLMGateway (OpenRouter)
                                                             â”‚
                                                              â–¼
                                                       TaskSnapshot & WebSocket Event
                                                              â”€
                                                              â–¼
                                                        Aspasia (Observer / TercÃ¼man)
```

- Karar MekanizmasÄ±: KararlarÄ± `PinealExecutor` ve `CognitiveRouter` verir.
- Aspasia: Sistemin karar vericisi deÄŸil; sistem durumunu, gÃ¼ven skorlarÄ±nÄ± ve telemetriyi doÀšµÈX[[Hİ[[±,Xñ,^XHpéñ,ZÛ^X[ˆğí›[XÚHÈ\˜ğïX[ˆ
ØœÙ\™\ŠHØ]X[±,Y1,\‹‚‹Hğï™[›ZÈ	ˆØ\ØNˆTH[˜Z\›\±,Hİ\[H˜^›1,H
[‹[Y[[ÜJH™Hœ[™X[İ˜][šœÛÛ˜ÜŞX\ñ,[™HØZÛ[±,\‹ˆØZH1ešYœ™[[YHYX[\±,H[Úİ\‹‚‚‹KKB‚ˆÈÈ‹ˆİ\[[H™H˜qgÛ]XB‚ˆÈÈÈÙ\™ZÜÚ[š[[\‚‹H]ÛˆËŒL
Â‹H›ÙKšœÈN
È
œ›Û[™péÚ[ŠB‹H^]ÜšYÚÚ›ÛZ][H
^]ÜšYÚ[œİ[Ú›ÛZ][X
B‚ˆÈÈÈKˆ]Ûˆ˜q'Ü[[1,[1,ZÛ\±,N‚˜˜\Úœ\[œİ[\ˆ™\]Z\™[Y[Ëœ^]ÜšYÚ[œİ[Ú›ÛZ][B˜‚ˆÈÈÈ‹ˆÛÛ™šYğï˜\Ş[Û‚˜œ[™X[İ˜][šœÛÛ˜™^XH™[˜ÜŞX\ñ,[˜HTH[˜Z\›\±,[³±,HZÛ^Z[‚˜œÛÛ‚Âˆ˜\WÚÙ^HˆœÚË[Ü‹]ŒKVSÕT—ÓÔS”“ÕUT—ÒÑVH‚ˆ]š[WÚÙ^Hˆ›KVSÕT—ÕU’SWÒÑVH‚ŸB˜‚ˆÈÈÈËˆ˜XÚÙ[™	ÚH˜qgÛ]XN‚˜˜\Úœ]Ûˆ[H]šXÛÜ›ˆ˜XÚÙ[™˜\N˜\KZÜİLËŒŒŒHK\Ü˜ŠŠ™^XHÚ[™İÜÈpéÚ[ˆğ&­rY[ˆ˜\Û]˜˜]0éØ[1,qgİ1,\±[Xš[\ŠJ‚‚ˆÈÈÈˆœ›Û[™	ÚH˜qgÛ]XN‚˜˜\Ú˜Ùœ›Û[™›œH[œİ[›œH[ˆ]‚˜‚‹KKB‚ˆÈÈËˆ\İ™Hñ'Ü[[XB‚ˆÈÈÈš\š[H™H[YÜ˜\Ş[Ûˆ\İ\šH
]\İ
N‚˜˜\Úœ]Ûˆ[H]\İ\İËÈ]‚˜ŠŠ0ïHLM\İZÙ]H0éØ[qgñ,\ˆ™Hñ'Ü[[±,\šJ‚‚ˆÈÈÈpéİ[ˆyØH
L‘JHš^\™H	ˆÛ˜\Úİ\İN‚Ø[›1,HSH™H[›1,ZÈ[[Y]šHZñ,qgñ,[±,Hğ&­r[[XZÚpéÚ[‚˜˜\Úœ]Ûˆ\İÙL™WÙš^\™KœB˜H\İ‚ŒKˆHZ˜[±,HØ[›1,HSH0éØq'Ü±,[,arÄ±yla sÄ±rayla koÅŸturur.
2. 12 adet anlÄ±k `TaskSnapshot` Ã¼retir.
3. `AgentRun` baÅŸlangÄ±Ã§/bitiÅŸ zamanlarÄ±nÄ± ve gÃ¼ven skorlarÄ±nÄ± kaydeder.
4. Aspasia'nÄ±n yapÄ±landÄ±rÄ±lmIÅŸ telemetriyi okumasÄ±nÄ± teyit eder.

---

## 4. Lisans ve Gizlilik
Bu yazÄ±lÄ±m araÉŸtÄ±rma ve analitik amaÃ§lÀ±dÄ±r.
