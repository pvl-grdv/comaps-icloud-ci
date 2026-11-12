# Open With probe evidence — 2026-11-12

The menu eligibility difference is observed. Successful URL delivery and a fully passing A/B experiment are **not established**. Probe polling/reruns are stopped. Actual CoMaps validation has a separate status.

Pinned source: `871febfffe0ef2a970d4f6973442dd80c632da01`, `iphone/Maps/CoMaps.plist`, SHA-256 `5781977ce31d3060208e0481be3bbe60ceca42de1326bafced5ae1f75275465a`. Exact GPX document/imported-UTI records were extracted (role absent; rank `Default`). Receiver bundle ID is the same in both arms; the positive control always uses YES. In run 43193416416 the built receiver plists differ **only** in `LSSupportsOpeningDocumentsInPlace`. Synthetic GPX SHA-256: `260f23ba98b295463f447690f7b83b81b8d7e58f9c697b30001a00d460385092`.

Environment: public `xcode-27` runner, Xcode 27.0 (27A266a), iOS 27.0 (24A434), iPhone 18 Pro Max simulator. This does not verify the reported physical iOS 27.3 beta behavior.

| Run / exact tested HEAD | NO job | YES job | Observation and limit |
|---|---|---|---|
| [43188726003](https://github.com/pvl-grdv/comaps-icloud-ci/actions/runs/43188726003)<br>`93e1475bbc36830132e71d3dd4c6b3dabe5adbc2` | failure | failure | Both fail compilation: missing SHA256 data: argument label. No XCTest or Files observation. |
| [43189372960](https://github.com/pvl-grdv/comaps-icloud-ci/actions/runs/43189372960)<br>`0b5570ede909ec95ae63992715f21e962e71f3c8` | failure | failure | Both build/boot; first GPXProbe installation times out at 30 s. No XCTest or Files observation. |
| [43190746576](https://github.com/pvl-grdv/comaps-icloud-ci/actions/runs/43190746576)<br>`9a9cf6f785abc1582cdfdc5c76420d1cdbdbd536` | failure | failure | NO reaches full menu and ordinary missing-receiver assertion, then xcodebuild is interrupted at 360 s. YES first installation times out at 120 s. Incomplete control. |
| [43193416416](https://github.com/pvl-grdv/comaps-icloud-ci/actions/runs/43193416416)<br>`6e5323bf38fd9a65b129abe4c5928d39c84d4942` | success | failure | NO is a completed, verified negative control. YES full menu contains Probe and foreground launch succeeds, but receipt remains WAITING; HARNESS_RECEIPT_NOT_READY. |
| [43196102950](https://github.com/pvl-grdv/comaps-icloud-ci/actions/runs/43196102950)<br>`4fd6371dda3e94a7d9c62b7f27497ad85cdfbf2c` | failure | failure | Both first non-handler GPXFixtures installs time out at 120 s; independent host/process diagnostics stall too. No XCTest, menu or callback trace. |

**All five workflows concluded failure.** NO job success in 43193416416 means the wrapper validated one ordinary `OPEN_WITH_RECEIVER_MISSING` failure: 1 test, 0 passed, 1 failed, 0 skipped, 0 expectedFailures, xcodebuild 65 and exact `TEST EXECUTE FAILED`. YES ran the same method, passed the visibility/foreground checks, then failed `HARNESS_RECEIPT_NOT_READY`; its final receipt label is `WAITING`. No received bytes or post-delivery source-preservation result exists.

Both run 43193416416 menus were visually inspected: NO shows GPX Control + Quick Look; YES shows GPX Control + GPX Probe + Quick Look. The keyboard tutorial is still visible below the complete receiver list.

| Image, run 43193416416 | Extracted-file SHA-256 |
|---|---|
| no menu — `open-with-probe-review-43193416416/no/attachments/33CA4005-B147-4CB0-A909-B49DFF822F4A.png` | `c0ccdcdb180643933e90a87ca652aec237c6e501f7669df898fffedbe5bb134d` |
| yes menu — `open-with-probe-review-43193416416/yes/attachments/3BE9255B-B566-4447-AEC1-F86061F6BFBD.png` | `600690717fc91f12ca545c7635e195a0d5df970e963eff1b5fb5074f9e4e6a97` |
| yes final receiver — `open-with-probe-review-43193416416/yes/attachments/F99A04A3-32E9-4433-8FF6-D8CF1EEBE5F1.png` | `5fcd08806871c3fe7e0008ed57aa5c63db7ad9a190872da72dcb168e61fcca4c` |

GitHub-reported artifact archive SHA-256 values (extracted images above were hashed locally; archive hashes below were not recomputed from ZIP bytes):

| Run | Arm / artifact ID | Archive SHA-256 |
|---|---|---|
| 43188726003 | no / 13928744627 | `ffbb160816db33ccdc23eb1ea95179ac6397f0b1d0fcc2fff58022c328bf68e6` |
| 43188726003 | yes / 13929198391 | `20732415d0f636380aef0e63abede87aced42cb844489b6ad960c2c455874798` |
| 43189372960 | no / 13930228307 | `99c74a8df046561399605879c8791b9ea80af726cc68df4d8ae76cedb0703ee9` |
| 43189372960 | yes / 13930475738 | `e48981ce9bf4d015329d2b6a43ce21f94e2bdffe5a27d4e17720bd47a36773d1` |
| 43190746576 | no / 13931178300 | `c8033d6290ac31963654beca874b273571e3acb186548b110fdf9b45c2f2199e` |
| 43190746576 | yes / 13930807138 | `bed5f8c3f870fd806b3780bbebc901a300fc2be887383d9d7fb9d45d55b040b9` |
| 43193416416 | no / 13931689535 | `89c21055bfa0385411753ec6709bce51dcaaea9566ec875d9d2c8d1cbe35a03f` |
| 43193416416 | yes / 13932546399 | `2903a61d427358ffe116e4925161e895905730ea146d4080901e4de9c4b6c009` |
| 43196102950 | no / 13933731529 | `6bc8afe465177551b88d15b50055ced5ca1ab247fdedb12cc76300a8761869e5` |
| 43196102950 | yes / 13934170542 | `678851b76f706874b6833e09ab52f1e7f2a71fb0cce5ab06a555d04b4ab82150` |

Latest limitation: both non-handler fixture installs timed out at 120 s. `sample` 10 s, `ps` 10 s, simulator listing 20 s and unified-log collection 30 s also timed out with empty outputs; shutdown/delete timed out. Disk had 35 GiB free and no swapouts were recorded. This supports an unresolved host/process-service stall, not a GPX registration diagnosis or a known exact service cause. No callback trace was reached.

Full source hashes, artifact expiry dates, relative evidence paths and primary-reference links are in `probe-history.json`. Individual `open-with-probe-review-<run>/` directories retain exact job logs, artifacts metadata, summaries where completed, and diagnoses. No assertions or diagnostic flags were changed for this consolidation.
