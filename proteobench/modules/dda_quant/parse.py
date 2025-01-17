from __future__ import annotations

from typing import Dict, List

import pandas as pd

from proteobench.modules.dda_quant.parse_settings import ParseSettings
from proteobench.modules.interfaces import ParseInputsInterface


class ParseInputs(ParseInputsInterface):
    def convert_to_standard_format(
        self, df: pd.DataFrame, parse_settings: ParseSettings
    ) -> tuple[pd.DataFrame, Dict[int, List[str]]]:
        """Convert a search engine output into a generic format supported by the module."""

        for k, v in parse_settings.mapper.items():
            if k not in df.columns:
                raise ImportError(
                    f"Column {k} not found in input dataframe. Please check input file and selected search engine."
                )

        df.rename(columns=parse_settings.mapper, inplace=True)

        replicate_to_raw = {}
        for k, v in parse_settings.replicate_mapper.items():
            try:
                replicate_to_raw[v].append(k)
            except KeyError:
                replicate_to_raw[v] = [k]

        if "Reverse" in parse_settings.mapper:
            df = df[df["Reverse"] != parse_settings.decoy_flag]

        df["contaminant"] = df["Proteins"].str.contains(parse_settings.contaminant_flag)
        for species, flag in parse_settings.species_dict.items():
            df[species] = df["Proteins"].str.contains(flag)
        df["MULTI_SPEC"] = (
            df[list(parse_settings.species_dict.keys())].sum(axis=1)
            > parse_settings.min_count_multispec
        )

        # If there is "Raw file" then it is a long format, otherwise short format
        if "Raw file" not in parse_settings.mapper.values():
            meltvars = parse_settings.replicate_mapper.keys()
            df = df.melt(
                id_vars=list(set(df.columns).difference(set(meltvars))),
                value_vars=meltvars,
                var_name="Raw file",
                value_name="Intensity",
            )
        df["replicate"] = df["Raw file"].map(parse_settings.replicate_mapper)
        df = pd.concat([df, pd.get_dummies(df["Raw file"])], axis=1)

        df = df[df["MULTI_SPEC"] == False]

        # TODO, if "Charge" is not available return a sensible error
        df.loc[df.index, "peptidoform"] = df.loc[df.index, "Sequence"]+"|Z="+df.loc[df.index, "Charge"].map(str)
        count_non_zero = (
            df.groupby(["Sequence", "Raw file"])["Intensity"].sum() > 0.0
        ).groupby(level=[0]).sum() == 6

        allowed_peptidoforms = list(count_non_zero.index[count_non_zero])
        filtered_df = df[df["Sequence"].isin(allowed_peptidoforms)]

        return filtered_df, replicate_to_raw
