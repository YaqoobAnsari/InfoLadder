# MSD test fixture

`1068.pickle` — one `graph_out` plan (native id 1068) from the **MSD (Modified
Swiss Dwellings)** train split, copied verbatim from
`data/raw/msd/graph_out/1068.pickle`.

Source: 4TU.ResearchData, dataset `e1d89cb5-6872-48fc-be63-aadd687ee6f9`
(`modified-swiss-dwellings-v1-train.zip`), ECCV 2024. **License: CC BY 4.0** —
redistribution permitted with attribution:

> C. van Engelenburg, F. Mostafavi, E. Kuhn, Y. Jeon, M. Franzen, M. Standfest,
> J. van Gemert, S. Khademi. "MSD: A Benchmark Dataset for Floor Plan Generation
> of Building Complexes." ECCV 2024. Dataset: doi 4TU e1d89cb5.

It is a `networkx.Graph`: 15 area nodes (room polygons + `room_type` + `centroid`),
14 access edges (`connectivity` ∈ {door, passage, entrance}). Used by
`tests/test_msd.py::test_fixture_end_to_end`. Full format + acquisition:
`docs/scout_reports/msd_2026-07-14.md` and `docs/DATA.md`.

Note: the `centroid` node attribute is a `torch.Tensor` in the shipped pickle, so
`torch` must be importable to unpickle (it is a project dependency).
