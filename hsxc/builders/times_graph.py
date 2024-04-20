# external imports
from typing import List, Tuple, Dict
from dataclasses import dataclass
from datetime import datetime, timedelta
import plotly.graph_objs as go
import plotly.offline as pyo

# hsxc imports
from hsxc import db
from hsxc.models.runner import Runner
from hsxc.models.result import Result
from hsxc.models.team import Team
from hsxc.models.league import League
from hsxc.helpers import CUR_YEAR


class RunnerGraphBuilder:

    def __init__(self, runner: Runner) -> None:
        self.runner = runner
        self.graph_html: str = None

    def build(self) -> str:
        """Return HTML div of Plotly graph of runner's times"""
        # abort if insufficient data
        if not self._has_sufficient_data():
            return None

        self._determine_min_max_day()
        self._build_traces()
        self._build_layout()
        self._build_figure()
        self._build_html()
        return self.graph_html

    def _has_sufficient_data(self) -> None:
        results: List[Result] = self.runner.results
        years = {res.race.date.year for res in results}
        res_by_year: Dict[str, List[Result]] = {
            year: [res for res in results if res.race.date.year == year] 
            for year in years
        }
        max_len = max([len(res_by_year[year]) for year in years])
        
        # sort results by date
        for year, res_list in res_by_year.items():
            res_by_year[year] = sorted(res_list, key=lambda r: r.race.date)

        self.years = sorted(list(years))
        self.res_by_year = res_by_year
        return max_len >= 2
    
    def _determine_min_max_day(self) -> None:
        min_day = datetime(CUR_YEAR, 12, 31)
        max_day = datetime(CUR_YEAR, 1, 1)
        for year, res_list in self.res_by_year.items():
            for res in res_list:
                dt = datetime(CUR_YEAR, res.race.date.month, res.race.date.day)
                if dt < min_day:
                    min_day = dt
                elif dt > max_day:
                    max_day = dt
        self.min_day = min_day - timedelta(days=5)
        self.max_day = max_day + timedelta(days=5)

    def _build_traces(self) -> None:
        markers = self._create_markers_by_year()
        last_year = max(self.years)
        traces = []
        for year, res_list in self.res_by_year.items():
            dts = [
                datetime(CUR_YEAR, res.race.date.month, res.race.date.day) 
                for res in res_list
            ]
            times = [res.adj_time() for res in res_list]
            traces.append(
                go.Scatter(
                    x=dts, y=times,
                    mode='markers+lines+text',
                    marker=markers[last_year - year],
                    name=year,
                    line=dict(width=4),
                    text=[''] * (len(dts) - 1) + [year],
                    textposition='middle right',
                    textfont=dict(size=14),
                    hovertext=self._format_hover_text(res_list),
                    hoverinfo='text',  # Show only custom text
                )
            )
        self.traces = traces

    def _create_markers_by_year(self) -> dict:
        colors = [
            (3 + (255-3)/5*i, 33 + (255-33)/5*i, 153 + (255-153)/5*i)
            for i in range(1, 6)
        ]
        colors = [f'rgb({int(r)},{int(g)},{int(b)})' for r,g,b in colors]
        colors = ['red'] + colors

        symbols = [
            'circle', 'square', 'triangle-up', 
            'triangle-down', 'star', 'circle'
        ]

        return {
            i: dict(
                color=colors[i],
                size=9,
                symbol=symbols[i],
                line=dict(width=2, color=colors[i])
            )
            for i in range(0,6)
        }

    def _format_hover_text(self, res_list: List[Result]) -> List[str]:
            return [f'{r.adj_time_f()} ({r.race.name_f()})' for r in res_list]

    def _build_layout(self) -> None:
        dates = self._set_x_axis_labels()
        times = self._set_y_axis_labels()

        self.layout = go.Layout(
            # title='Times through the Season',
            xaxis=dict(
                title='Date',
                range=dates['range'],
                tickvals=dates['vals'],
                ticktext=dates['txt'],
            ),
            yaxis=dict(
                title='Course Adj Time',
                range=times['range'],
                tickvals=times['vals'],
                ticktext=times['txt'],
            )
        )

    def _set_x_axis_labels(self) -> None:
        dts = self._split_into_7_dates_by_halving(self.min_day, self.max_day)
        dts_txt = [dt.strftime('%b %d') for dt in dts]
        return {
            'vals': dts,
            'txt': dts_txt,
            'range': [self.min_day, self.max_day],
        }

    def _split_into_7_dates_by_halving(self, 
        min_day: datetime, 
        max_day: datetime
    ) -> List[datetime]:
        mid = min_day + timedelta(days=int((max_day - min_day).days / 2))

        q1 = min_day + timedelta(days=int((mid - min_day).days / 2))
        q3 = mid + timedelta(days=int((max_day - mid).days / 2))

        d1 = min_day + timedelta(days=int((q1 - min_day).days / 2))
        d2 = q1 + timedelta(days=int((mid - q1).days / 2))
        d3 = mid + timedelta(days=int((q3 - mid).days / 2))
        d4 = q3 + timedelta(days=int((max_day - q3).days / 2))

        return [d1, q1, d2, mid, d3, q3, d4]

    def _set_y_axis_labels(self) -> None:
        min_time = min([res.adj_time() for res in self.runner.results])
        min_mins = int(min_time / 60000)
        max_time = max([res.adj_time() for res in self.runner.results])
        max_mins = int(max_time / 60000) + 1
        return {
            'vals': [i * 60000 for i in range(min_mins, max_mins + 1)],
            'txt': [f'{i:02d}:00' for i in range(min_mins, max_mins + 1)],
            'range': [min_mins * 60000, max_mins * 60000],
        }

    def _build_figure(self) -> None:
        self.figure = go.Figure(data=self.traces, layout=self.layout)

    def _build_html(self) -> None:
        self.graph_html = pyo.plot(
            self.figure, 
            include_plotlyjs=True, 
            output_type='div'
        )
