import json
import urllib.parse

def generate_chart_url(labels: list, data: list, title: str, color: str = "rgb(75, 192, 192)") -> str:
    """Generate a QuickChart.io URL for a bar/line chart."""
    chart_config = {
        "type": "bar",
        "data": {
            "labels": labels,
            "datasets": [{
                "label": title,
                "data": data,
                "backgroundColor": color,
                "borderColor": color,
                "borderWidth": 1
            }]
        },
        "options": {
            "title": {
                "display": True,
                "text": title
            },
            "scales": {
                "yAxes": [{
                    "ticks": {
                        "beginAtZero": True
                    }
                }]
            }
        }
    }
    
    config_json = json.dumps(chart_config)
    encoded_config = urllib.parse.quote(config_json)
    return f"https://quickchart.io/chart?c={encoded_config}&w=600&h=400&bkg=white"
