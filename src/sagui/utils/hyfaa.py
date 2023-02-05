from datetime import datetime, timedelta, timezone
import numpy as np

# lambda function, CNES Julian days to Gregorian date and vice-versa
julianday_to_datetime = lambda t: datetime(1950, 1, 1, tzinfo=timezone.utc) + timedelta(int(t))
datetime_to_julianday = lambda t: (t - datetime(1950, 1, 1, tzinfo=timezone.utc)).total_seconds() / (24. * 3600.)
vfunc_jd_to_dt = np.vectorize(julianday_to_datetime)
