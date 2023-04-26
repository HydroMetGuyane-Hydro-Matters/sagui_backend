import fiona
from glob import glob
import numpy as np
import rasterio
from rasterio.mask import mask

from django.conf import settings

from sagui import models


def get_global_alert_info():
    # Load the latest file of atmo data and compute stats & alert code
    raw_atom_files_path = f"{settings.SAGUI_SETTINGS.get('SAGUI_PATH_TO_ATMO_FILES', '')}/../raw"
    last_raw_atom_file = sorted(glob(f'{raw_atom_files_path}/*.tif'))[-1]
    zoi_path = f"{settings.SAGUI_SETTINGS.get('SAGUI_DATA_PATH', '')}/zoi.geojson"
    # Open and filter the raster using the vector mask (geojson expected).

    with fiona.open(zoi_path, "r") as shapefile:
        geoms = [feature["geometry"] for feature in shapefile]
        with rasterio.open(last_raw_atom_file) as input:
            # shape_mask, transform, window = raster_geometry_mask(input, geoms)
            out_image, out_transform = mask(input, geoms, filled=False)
            values = out_image.compressed()
            values.sort()
            stats = get_stats(values)
            histogram = get_histogram(values)

            # compute alert code
            alert_categories = models.AtmoAlertCategories.objects.all().order_by('-bounds_min')
            alert_value = stats['10th_max']['value']
            alert_code = None
            # We cannot use idx in the loop for some reason, so doing it manually
            idx = len(alert_categories) - 1
            for c in alert_categories:
                if alert_value > c.bounds_min:
                    alert_code = idx
                    alert_cat = c
                    break
                # decrease index
                idx = idx - 1

            return {
                'global_alert_level': f'a{alert_code}',
                'global_alert_cat': alert_cat,
                'histogram': histogram,
                'stats': stats,
            }
    return None


def get_stats(values):
    """
    Filter the given raster using the vector mask (geojson expected). Then compute the value that will be used to produce an alert and write it into file
    :param rast: atomspheric pollution raster data
    :param mask_path: path to the mask of "zones of interest" (populated places), expected is a geojson file
    :return:
    """
    perc = np.percentile(values, [50,75,90,95,99])
    stats = {
        'max' : {
            'value': values.max(),
            'description': 'Max value',
        },
        '10th_max' : {
            'value': values[-10],
            'description': '10th bigger value (removes the 9 first values, to smooth the extremes)',
        },
        'mean' : {
            'value': values.mean(),
            'description': 'Mean value',
        },
        'median' : {
            'value': perc[0],
            'description': 'Median value',
        },
        'percentile_99' : {
            'value': perc[4],
            'description': '99th percentile',
        },
        'percentile_95' : {
            'value': perc[3],
            'description': '95th percentile',
        },
        'percentile_90' : {
            'value': perc[2],
            'description': '90th percentile',
        },
    }
    return stats


def get_histogram(values):
    # Compute the repartition of the pixels across the atmo alert categories
    # Use numpy histogram to sort the values into the given bins (alert levels)
    alert_categories = models.AtmoAlertCategories.objects.all().order_by('bounds_min')
    bins = [l.bounds_min for l in alert_categories] + [alert_categories.last().bounds_max]
    histo = np.histogram(values, bins=bins)

    # Initiate atmo_histo object
    atmo_histo = {}
    # and fill it with the data from the histogram
    for idx, x in enumerate(histo[0]):
        atmo_histo[f'a{idx}'] = x
    return atmo_histo

