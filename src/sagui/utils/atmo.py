import rasterio
from rasterio.mask import mask,raster_geometry_mask
import fiona
import numpy as np

def stats(rast_path, mask_path):
    """
    Filter the given raster using the vector mask (geojson expected). Then compute the value that will be used to produce an alert and write it into file
    :param rast: atomspheric pollution raster data
    :param mask_path: path to the mask of "zones of interest" (populated places), expected is a geojson file
    :return:
    """
    with fiona.open(mask_path, "r") as shapefile:
        geoms = [feature["geometry"] for feature in shapefile]

        with rasterio.open(rast_path) as input:
            # shape_mask, transform, window = raster_geometry_mask(input, geoms)
            out_image, out_transform = mask(input, geoms, filled=False)
            values = out_image.compressed()
            values.sort()
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
    return None

