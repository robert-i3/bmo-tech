import flask
from flask import Flask, request
import urllib.request
import json
import pandas as pd
import math
from datetime import datetime, date

app = Flask(__name__)

# Constants
FX_SERIES_NAME = "FXCADUSD"
CORRA_SERIES_NAME = "AVG.INTWO"

VAL_COL_PREFIX = "Value_"
DATE_COL = "Date"

DATE_FORMAT = "%Y-%m-%d"


def date_from_string(date_string: str) -> date:
    """Get date object from string of form YYYY-MM-dd"""

    return datetime.strptime(date_string, DATE_FORMAT).date() if date_string is not None else None


def get_df(series_name: str, from_date: date, to_date: date) -> pd.DataFrame:
    """Produces a pandas dataframe of Dates and corresponding Values for the given series

    :param series_name: The name of the series that the data is to be requested for, e.g. "FXCADUSD"
    :param from_date: The start of the date range for which the data should be requested (inclusive)
    :param to_date: The end of the date range for which the data should be requested (inclusive)
    :returns: Pandas DateFrame with columns Date (containing the date of the observation), and Value_&lt;series_name&gt;
    (containing the value of the observation).

    """

    # See https://www.bankofcanada.ca/valet/docs for details
    valet_request_url = "http://www.bankofcanada.ca/valet/observations/" + series_name +\
                        "/json?start_date=" + from_date.strftime(DATE_FORMAT) +\
                        "&end_date=" + to_date.strftime(DATE_FORMAT)
    valet_response = urllib.request.urlopen(valet_request_url)
    response_dict = json.load(valet_response)
    observations = response_dict["observations"]

    df = pd.DataFrame(columns=[DATE_COL, VAL_COL_PREFIX + series_name])
    for observation in observations:
        obs_date = date_from_string(observation["d"])
        obs_value = float(observation[series_name]["v"])
        df.loc[len(df.index)] = [obs_date, obs_value]

    return df


@app.route("/fx-corra-stats")
def fx_corra_stats():
    """Expects request of the form localhost.localdomain/fx-corra-stats?fromdate=YYYY-MM-dd&todate=YYYY-MM-dd"""

    from_date = date_from_string(request.args.get("fromdate", None))
    to_date = date_from_string(request.args.get("todate", None))

    if from_date is not None and to_date is not None and from_date <= to_date:
        df_fx_rates = get_df(FX_SERIES_NAME, from_date, to_date)
        df_corra = get_df(CORRA_SERIES_NAME, from_date, to_date)

        # (Just in case we have missing observations for one series but not the other):
        # We only consider dates for which we have observations for both USD/CAD and CORRA
        # This was not specified in the assignment, but is a reasonable assumption since we need corresponding
        # observations for the Pearson coefficient. We could calculate the min/max/mean on the individual dataframes,
        # but then we could have a mismatch between the individual stats and the Pearson coefficient, which
        # could be misleading.
        intersect_df = df_fx_rates.set_index(DATE_COL).join(df_corra.set_index(DATE_COL), how="inner")

        fx_vals = intersect_df[VAL_COL_PREFIX + FX_SERIES_NAME]
        min_fx_rate = min(fx_vals)
        max_fx_rate = max(fx_vals)
        mean_fx_rate = sum(fx_vals) / len(fx_vals)

        corra_vals = intersect_df[VAL_COL_PREFIX + CORRA_SERIES_NAME]
        min_corra = min(corra_vals)
        max_corra = max(corra_vals)
        mean_corra = sum(corra_vals) / len(corra_vals)

        # Pearson coefficient calculation
        # (sum(x_i - x_bar) * sum(y_i - y_bar)) / (sqrt(sum((x_i - x_bar)^2)) * sqrt(sum((y_i - y_bar)^2)))
        numerator = 0
        x_under_root = 0
        y_under_root = 0
        for i in range(0, len(fx_vals)):
            xi_minus_xbar = fx_vals[i] - mean_fx_rate
            yi_minus_ybar = corra_vals[i] - mean_corra
            numerator += xi_minus_xbar * yi_minus_ybar

            x_under_root += xi_minus_xbar ** 2
            y_under_root += yi_minus_ybar ** 2

        denominator = math.sqrt(x_under_root) * math.sqrt(y_under_root)
        pearson_coeff = numerator / denominator

        results_dict = {
            "min_fx_rate": min_fx_rate,
            "max_fx_rate": max_fx_rate,
            "mean_fx_rate": mean_fx_rate,
            "min_corra": min_corra,
            "max_corra": max_corra,
            "mean_corra": mean_corra,
            "pearson_coeff": pearson_coeff,
            "status": 0
        }
    else:
        results_dict = {"status": 1}

    response = flask.jsonify(results_dict)
    response.headers.add('Access-Control-Allow-Origin', '*')
    return response
