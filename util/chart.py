from quickchart import QuickChart
from datetime import datetime
from dateutil.relativedelta import relativedelta
from pprint import pprint, pformat
import sys


def individual_hours_chart(
    months: dict, cutoff_months: int = 6, short_url: bool = True
) -> str:
    """Return a quickchart URL for the given hours data.

    `months` is a dict with keys in YYYY-MM format and values in hours.
    `cutoff_months` is the number of months to show, counting backwards from the current month.
    `short_url` controls whether to return a shortened URL or the full URL. (Default: True)

    Returns a string URL to the generated chart.
    `"""

    # The system was started in September 2025, there's no data before that.
    absolute_cutoff = datetime(2025, 9, 1)

    # Prepare the chart data
    # We want to show the last `cutoff_months` months and add empty months if necessary
    # months keys are in YYYY-MM format
    processing_month = datetime.now()

    data = {"labels": [], "data": []}

    for i in range(cutoff_months):
        data["labels"].append(processing_month.strftime("%b"))
        month_key = processing_month.strftime("%Y-%m")
        data["data"].append(months.get(month_key, 0))
        # Move to previous month
        processing_month -= relativedelta(months=1)

        if processing_month < absolute_cutoff:
            break

    data["labels"].reverse()
    data["data"].reverse()

    # Since we use a JS function here we have to pass the config as a string rather than a dict
    qc = QuickChart()
    qc.width = 500
    qc.height = 300
    qc.version = "2"
    qc.background_color = "rgba(26, 29, 33, 1)"  # Match Slack dark mode

    # Config can be set as a string or as a nested dict
    conf = """{
    type: 'line',
    data: {
        labels: {labels},
        datasets: [{
        data: {data},
        fill: true,
        borderColor: getGradientFillHelper('vertical', ['#eb3639', '#a336eb', '#36a2eb']),
        borderWidth: 5,
        pointRadius: 5, // need points visible for labels
        backgroundColor: 'rgba(255, 255, 255, 0.1)', 
        }]
    },
    options: {
        layout: {
        padding: {
            top: 50,
            right: 20,
            left: 20
        }
        },
        legend: {
        display: false
        },
        scales: {
        xAxes: [{
            display: true,
            gridLines: {
            display: false,
            },
            ticks: {
            fontColor: '#fff'
            }
        }],
        yAxes: [{
            display: false,
            gridLines: {
            display: false,
            },
            ticks: {
                beginAtZero: true,
            }
        }]
        },
        plugins: {
        datalabels: {
            align: 'top',
            anchor: 'end',
            color: '#fff',
            font: {
            weight: 'bold',
            size: 12
            },
            formatter: function(value) {
            return value + 'h';
            }
        }
        }
    },
    plugins: ["chartjs-plugin-datalabels"]
    }"""

    conf = conf.replace("{labels}", str(data["labels"]))
    conf = conf.replace("{data}", str(data["data"]))

    # Remove all whitespace for URL size reasons

    qc.config = conf  # type: ignore

    if short_url:
        url = qc.get_short_url()
    else:
        url = qc.get_url()

    return url
