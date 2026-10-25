# Licences of the text on this Space

The viewer code (`index.html`, `app.js`, `style.css`) and the recorded answers, questions and notes are part of [provenance-tiered-rag](https://github.com/NecmiKural/provenance-tiered-rag), under the MIT licence: Copyright (c) 2026 Necmi Kural.

The passages quoted in `nz-gst.json`, `de-vat.json` and `nz-immigration.json` come from the sources below, each under its own terms. Every licence line below is copied from `sources.toml`, and `tests/test_evidence.py` fails if one is missing. Each passage in the viewer names its source and the dates it was in force.

## New Zealand GST

- **Goods and Services Tax Act 1985** (statute), from [legislation.govt.nz](https://www.legislation.govt.nz/act/public/1985/141/en/). No copyright in New Zealand legislation (Copyright Act 1994, s 27). Cut into subsections, each dated by the consolidations that show it.
- **Inland Revenue GST guidance** (official guidance), from [ird.govt.nz/gst](https://www.ird.govt.nz/gst/), retrieved 2026-10-19. Crown copyright, Inland Revenue. Text reproduced under CC BY 4.0; logos and images excluded. Licence: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Changes: cut into one passage per heading; whitespace normalised.
- **Forum posts and practitioner notes** (untrusted notes). Written for this project (MIT). Some carry prompt-injection payloads on purpose.

## Germany

- **Umsatzsteuergesetz (UStG)** and **Umsatzsteuer-Durchführungsverordnung (UStDV)** (statute), from [gesetze-im-internet.de](https://www.gesetze-im-internet.de/ustg_1980/), retrieved 2026-10-22. Amtliches Werk ohne urheberrechtlichen Schutz (§ 5 Abs. 1 UrhG). Cut into one passage per paragraph and, for § 4, per listed exemption.
- **Forenbeiträge und Notizen** (untrusted notes). Written for this project (MIT). Some carry prompt-injection payloads on purpose.

## New Zealand immigration

- **Immigration Act 2009** (statute), from [legislation.govt.nz](https://www.legislation.govt.nz/act/public/2009/51/en/). No copyright in New Zealand legislation (Copyright Act 1994, s 27).
- **Immigration New Zealand Operational Manual** (official guidance), from [immigration.govt.nz/opsmanual](https://www.immigration.govt.nz/opsmanual/), retrieved 2026-10-22. Crown copyright, Ministry of Business, Innovation and Employment. Text reproduced under CC BY 3.0 NZ; logos and design excluded. Licence: [CC BY 3.0 NZ](https://creativecommons.org/licenses/by/3.0/nz/). Changes: cut into the instruction's own parts, with tables flattened to lines.
- **Migrant forum posts and notes** (untrusted notes). Written for this project (MIT). Some carry prompt-injection payloads on purpose.

Nothing here is tax or immigration advice, and none of these bodies endorses this project.
