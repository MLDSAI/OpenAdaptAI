"""Computer vision module."""

from loguru import logger
from PIL import Image, ImageDraw, ImageFont
from scipy.ndimage import binary_fill_holes
from skimage.metrics import structural_similarity as ssim
import cv2
import math
import numpy as np

from openadapt import cache, utils


@cache.cache()
def get_masks_from_segmented_image(segmented_image: Image.Image) -> list[np.ndarray]:
    """Process the image to find unique masks based on color channels.

    Args:
        segmented_image: A PIL.Image object of the segmented image.

    Returns:
        A list of numpy.ndarrays, each representing a unique mask.
    """
    logger.info("starting...")
    segmented_image_np = np.array(segmented_image)

    # Assume the last channel is the alpha channel if the image has 4 channels
    if segmented_image_np.shape[2] == 4:
        segmented_image_np = segmented_image_np[:, :, :3]

    # Find unique colors in the image, each unique color corresponds to a unique mask
    unique_colors = np.unique(
        segmented_image_np.reshape(-1, segmented_image_np.shape[2]), axis=0
    )
    logger.info(f"{len(unique_colors)=}")

    masks = []
    for color in unique_colors:
        # Create a mask for each unique color
        mask = np.all(segmented_image_np == color, axis=-1)
        masks.append(mask)

    logger.info(f"{len(masks)=}")
    return masks


@cache.cache()
def filter_masks_by_size(
    masks: list[np.ndarray],
    min_mask_size: tuple[int, int] = (15, 15),
) -> list[np.ndarray]:
    """Filter masks based on minimum size using the bounding box of "on" pixels.

    Args:
        masks: A list of numpy.ndarrays, each representing a mask.
        min_mask_size: A tuple specifying the minimum dimensions (height, width) that
            the bounding box of the "on" pixels must have to be retained.

    Returns:
        A list of numpy.ndarrays, each representing a mask that meets the size criteria.
    """
    size_filtered_masks = []
    for mask in masks:
        coords = np.argwhere(mask)  # Get coordinates of all "on" pixels
        if coords.size > 0:
            y_min, x_min = coords.min(axis=0)
            y_max, x_max = coords.max(axis=0)
            height = y_max - y_min + 1
            width = x_max - x_min + 1
            if height >= min_mask_size[0] and width >= min_mask_size[1]:
                size_filtered_masks.append(mask)
    return size_filtered_masks


@cache.cache()
def refine_masks(masks: list[np.ndarray]) -> list[np.ndarray]:
    """Refine the list of masks.

    - Fill holes of any size.
    - Remove masks completely contained within other masks.
    - Exclude masks where the convex hull does not meet a specified minimum
      size in any dimension.

    Args:
        masks: A list of numpy.ndarrays, each representing a mask.
        min_mask_size: A tuple specifying the minimum dimensions (height,
            width) that the convex hull of a mask must have to be retained.

    Returns:
        A list of numpy.ndarrays, each representing a refined mask.
    """
    logger.info(f"{len(masks)=}")

    masks = remove_border_masks(masks)
    masks = filter_thin_ragged_masks(masks)

    # Fill holes in each mask
    filled_masks = [binary_fill_holes(mask).astype(np.uint8) for mask in masks]

    size_filtered_masks = filter_masks_by_size(filled_masks)

    # Remove masks completely contained within other masks
    refined_masks = []
    for i, mask_i in enumerate(size_filtered_masks):
        contained = False
        for j, mask_j in enumerate(size_filtered_masks):
            if i != j:
                # Check if mask_i is completely contained in mask_j
                if np.array_equal(mask_i & mask_j, mask_i):
                    contained = True
                    break
        if not contained:
            refined_masks.append(mask_i)

    logger.info(f"{len(refined_masks)=}")
    return refined_masks


@cache.cache()
def filter_thin_ragged_masks(
    masks: list[np.ndarray],
    kernel_size: int = 3,
    iterations: int = 5,
) -> list[np.ndarray]:
    """Applies morphological operations to filter out thin and ragged masks.

    Args:
        masks: A list of ndarrays, where each ndarray is a binary mask.
        kernel_size: Size of the structuring element.
        iterations: Number of times the operation is applied.

    Returns:
        A list of ndarrays with thin and ragged masks filtered out.
    """
    logger.info(f"{len(masks)=}")
    kernel = np.ones((kernel_size, kernel_size), np.uint8)
    filtered_masks = []

    for mask in masks:
        # Convert boolean mask to uint8
        mask_uint8 = mask.astype(np.uint8) * 255
        # Perform erosion
        eroded_mask = cv2.erode(mask_uint8, kernel, iterations=iterations)
        # Perform dilation
        dilated_mask = cv2.dilate(eroded_mask, kernel, iterations=iterations)

        # Convert back to boolean mask and add to the filtered list
        filtered_masks.append(dilated_mask > 0)

    logger.info(f"{len(filtered_masks)=}")
    return filtered_masks


@cache.cache()
def remove_border_masks(
    masks: list[np.ndarray],
    threshold_percent: float = 5.0,
) -> list[np.ndarray]:
    """Removes masks whose "on" pixels are close to the mask borders on all four sides.

    Args:
        masks: A list of ndarrays, where each ndarray is a binary mask.
        threshold_percent: A float indicating how close the "on" pixels can be to
              the border, represented as a percentage of the mask's dimensions.

    Returns:
    - A list of ndarrays with the border masks removed.
    """

    def is_close_to_all_borders(mask: np.ndarray, threshold: float) -> bool:
        # Determine actual threshold in pixels based on the percentage
        threshold_rows = int(mask.shape[0] * (threshold_percent / 100))
        threshold_cols = int(mask.shape[1] * (threshold_percent / 100))

        # Check for "on" pixels close to each border
        top = np.any(mask[:threshold_rows, :])
        bottom = np.any(mask[-threshold_rows:, :])
        left = np.any(mask[:, :threshold_cols])
        right = np.any(mask[:, -threshold_cols:])

        # If "on" pixels are close to all borders, return True
        return top and bottom and left and right

    logger.info(f"{len(masks)=}")

    filtered_masks = []
    for mask in masks:
        # Only add mask if it is not close to all borders
        if not is_close_to_all_borders(mask, threshold_percent):
            filtered_masks.append(mask)

    logger.info(f"{len(filtered_masks)=}")
    return filtered_masks


@cache.cache()
def extract_masked_images(
    original_image: Image.Image,
    masks: list[np.ndarray],
) -> list[Image.Image]:
    """Apply each mask to the original image.

    Resize the image to fit the mask's bounding box, discarding pixels outside the mask.

    Args:
        original_image: A PIL.Image object of the original image.
        masks: A list of numpy.ndarrays, each representing a refined mask.

    Returns:
        A list of PIL.Image objects, each cropped to the mask's bounding box and
        containing the content of the original image within that mask.
    """
    logger.info(f"{len(masks)=}")
    original_image_np = np.array(original_image)
    masked_images = []

    for mask in masks:
        # Find the bounding box of the mask
        rows = np.any(mask, axis=1)
        cols = np.any(mask, axis=0)
        rmin, rmax = np.where(rows)[0][[0, -1]]
        cmin, cmax = np.where(cols)[0][[0, -1]]

        # Crop the mask and the image to the bounding box
        cropped_mask = mask[rmin : rmax + 1, cmin : cmax + 1]
        cropped_image = original_image_np[rmin : rmax + 1, cmin : cmax + 1]

        # Apply the mask
        masked_image = np.where(cropped_mask[:, :, None], cropped_image, 0).astype(
            np.uint8
        )
        masked_images.append(Image.fromarray(masked_image))

    logger.info(f"{len(masked_images)=}")
    return masked_images


@cache.cache()
def calculate_bounding_boxes(
    masks: list[np.ndarray],
) -> tuple[list[dict[str, float]], list[tuple[float, float]]]:
    """Calculate bounding boxes and centers for each mask in the list separately.

    Args:
        masks: A list of numpy.ndarrays, each representing a mask.

    Returns:
        A tuple containing two lists:
        - The first list contains dictionaries, each containing the "top",
          "left", "height", "width" of the bounding box for each mask.
        - The second list contains tuples, each representing the "center" as a
          tuple of (x, y) for each mask.
    """
    bounding_boxes = []
    centroids = []
    for mask in masks:
        # Find all indices where mask is True
        rows, cols = np.where(mask)
        if len(rows) == 0 or len(cols) == 0:  # In case of an empty mask
            bounding_boxes.append({})
            centroids.append((float("nan"), float("nan")))
            continue

        # Calculate bounding box
        top, left = rows.min(), cols.min()
        height, width = rows.max() - top, cols.max() - left

        # Calculate center
        center_x, center_y = left + width / 2, top + height / 2

        # Append data to the lists
        bounding_boxes.append(
            {
                "top": float(top),
                "left": float(left),
                "height": float(height),
                "width": float(width),
            }
        )
        centroids.append((float(center_x), float(center_y)))

    return bounding_boxes, centroids


def display_binary_images_grid(
    images: list[np.ndarray],
    grid_size: tuple[int, int] | None = None,
    margin: int = 10,
) -> None:
    """Display binary arrays as images on a grid with separation between grid cells.

    Args:
        images: A list of binary numpy.ndarrays.
        grid_size: Optional tuple (rows, cols) indicating the grid size.
            If not provided, a square grid size will be calculated.
        margin: The margin size between images in the grid.
    """
    if grid_size is None:
        grid_size = (int(np.ceil(np.sqrt(len(images)))),) * 2

    # Determine max dimensions of images in the list
    max_width = max(image.shape[1] for image in images) + margin
    max_height = max(image.shape[0] for image in images) + margin

    # Create a new image with a white background
    total_width = max_width * grid_size[1] + margin
    total_height = max_height * grid_size[0] + margin
    grid_image = Image.new("1", (total_width, total_height), 1)

    for index, binary_image in enumerate(images):
        # Convert ndarray to PIL Image
        img = Image.fromarray(binary_image.astype(np.uint8) * 255, "L").convert("1")
        img_with_margin = Image.new("1", (img.width + margin, img.height + margin), 1)
        img_with_margin.paste(img, (margin // 2, margin // 2))

        # Calculate the position on the grid
        row, col = divmod(index, grid_size[1])
        x = col * max_width + margin // 2
        y = row * max_height + margin // 2

        # Paste the image into the grid
        grid_image.paste(img_with_margin, (x, y))

    # Display the grid image
    grid_image.show()


def display_images_table_with_titles(
    images: list[Image.Image],
    titles: list[str] | None = None,
    margin: int = 10,
    fontsize: int = 20,
) -> None:
    """Display RGB PIL.Images in a table layout with titles to the right of each image.

    Args:
        images: A list of RGB PIL.Images.
        titles: An optional list of strings containing titles for each image.
        margin: The margin size in pixels between images and their titles.
        fontsize: The size of the title font.
    """
    if titles is None:
        titles = [""] * len(images)
    elif len(titles) != len(images):
        raise ValueError("The length of titles must match the length of images.")

    font = utils.get_font("Arial.ttf", fontsize)

    # Calculate the width and height required for the composite image
    max_image_width = max(image.width for image in images)
    total_height = sum(image.height for image in images) + margin * (len(images) - 1)
    max_title_height = fontsize + margin  # simple approach to calculating title height
    max_title_width = max(font.getsize(title)[0] for title in titles) + margin

    composite_image_width = max_image_width + max_title_width + margin * 3
    composite_image_height = max(
        total_height, max_title_height * len(images) + margin * (len(images) - 1)
    )

    # Create a new image to composite everything onto
    composite_image = Image.new(
        "RGB", (composite_image_width, composite_image_height), "white"
    )
    draw = ImageDraw.Draw(composite_image)

    current_y = 0
    for image, title in zip(images, titles):
        # Paste the image
        composite_image.paste(image, (margin, current_y))
        # Draw the title
        draw.text(
            (
                max_image_width + 2 * margin,
                current_y + image.height // 2 - fontsize // 2,
            ),
            title,
            fill="black",
            font=font,
        )
        current_y += image.height + margin

    composite_image.show()


def get_image_similarity(
    im1: Image.Image,
    im2: Image.Image,
    grayscale: bool = False,
    win_size: int = 7  # Default window size for SSIM
) -> tuple[float, np.array]:
    """Calculate the structural similarity index (SSIM) between two images.

    This function resizes the images to a common size maintaining their aspect ratios,
    and computes the SSIM either in grayscale or across each color channel separately.

    Args:
        im1 (Image.Image): The first image to compare.
        im2 (Image.Image): The second image to compare.
        grayscale (bool): If True, convert images to grayscale. Otherwise, compute
            SSIM on color channels.
        win_size (int): Window size for SSIM calculation. Must be odd and less than or
            equal to the smaller side of the images.

    Returns:
        tuple[float, np.array]: A tuple containing the SSIM and the difference image.
    """
    # Calculate aspect ratios
    aspect_ratio1 = im1.width / im1.height
    aspect_ratio2 = im2.width / im2.height

    # Determine the minimum dimension size based on win_size, ensuring minimum size to
    # avoid win_size error
    min_dim_size = max(2 * win_size + 1, 7)

    # Calculate scale factors to ensure both dimensions are at least min_dim_size
    scale_factor1 = max(min_dim_size / im1.width, min_dim_size / im1.height, 1)
    scale_factor2 = max(min_dim_size / im2.width, min_dim_size / im2.height, 1)

    # Calculate common dimensions that accommodate both images
    target_width = max(int(im1.width * scale_factor1), int(im2.width * scale_factor2))
    target_height = max(int(im1.height * scale_factor1), int(im2.height * scale_factor2))

    # Resize images to these new common dimensions
    im1 = im1.resize((target_width, target_height), Image.LANCZOS)
    im2 = im2.resize((target_width, target_height), Image.LANCZOS)

    if grayscale:
        # Convert images to grayscale
        im1 = np.array(im1.convert("L"))
        im2 = np.array(im2.convert("L"))
        data_range = max(im1.max(), im2.max()) - min(im1.min(), im2.min())
        mssim, diff_image = ssim(im1, im2, win_size=win_size, data_range=data_range, full=True)
    else:
        # Compute SSIM on each channel separately and then average the results
        mssims = []
        diff_images = []
        for c in range(3):  # Assuming RGB images
            im1_c = np.array(im1)[:, :, c]
            im2_c = np.array(im2)[:, :, c]
            data_range = max(im1_c.max(), im2_c.max()) - min(im1_c.min(), im2_c.min())
            ssim_c, diff_c = ssim(im1_c, im2_c, win_size=win_size, data_range=data_range, full=True)
            mssims.append(ssim_c)
            diff_images.append(diff_c)

        # Average the SSIM and create a mean difference image
        mssim = np.mean(mssims)
        diff_image = np.mean(diff_images, axis=0)

    return mssim, diff_image

@cache.cache()
def get_similar_image_idxs(
    images: list[Image.Image],
    min_ssim: float,
    size_similarity_threshold: float,
    short_circuit_ssim: bool = True
) -> tuple[list[list[int]], list[int], list[list[float]], list[list[float]]]:
    """
    Get images having Structural Similarity Index Measure (SSIM) above a threshold,
    and return the SSIM and size similarity matrices. Also returns indices of images not
    in any group. Optionally skips SSIM computation if the size difference exceeds the
    threshold.

    Args:
        images: A list of PIL.Image objects to compare.
        min_ssim: The minimum threshold for the SSIM for images to be considered
            similar.
        size_similarity_threshold: Minimum required similarity in size as a fraction
            (e.g., 0.9 for 90% similarity required).
        short_circuit_ssim: If True, skips SSIM calculation when size similarity is
            below the threshold.

    Returns:
        A tuple containing four elements:
        - A list of lists, where each sublist contains indices of images in the input
          list that are similar to each other above the given SSIM and size thresholds.
        - A list of indices of images not part of any group.
        - A matrix of SSIM values between each pair of images.
        - A matrix of size similarity values between each pair of images.
    """
    num_images = len(images)
    already_compared = set()
    similar_groups = []
    ssim_matrix = [[0.0] * num_images for _ in range(num_images)]
    size_similarity_matrix = [[0.0] * num_images for _ in range(num_images)]
    all_indices = set(range(num_images))

    for i in range(num_images):
        ssim_matrix[i][i] = 1.0
        size_similarity_matrix[i][i] = 1.0
        for j in range(i + 1, num_images):
            size_sim = get_size_similarity(images[i], images[j])
            size_similarity_matrix[i][j] = size_similarity_matrix[j][i] = size_sim

            if not short_circuit_ssim or size_sim >= size_similarity_threshold:
                s_ssim, _ = get_image_similarity(images[i], images[j])
                ssim_matrix[i][j] = ssim_matrix[j][i] = s_ssim
            else:
                ssim_matrix[i][j] = ssim_matrix[j][i] = math.nan

    for i in range(num_images):
        if i in already_compared:
            continue
        current_group = [i]
        for j in range(i + 1, num_images):
            if j in already_compared:
                continue
            if (
                ssim_matrix[i][j] >= min_ssim and
                size_similarity_matrix[i][j] >= size_similarity_thresholdi
            ):
                current_group.append(j)
                already_compared.add(j)

        if len(current_group) > 1:
            similar_groups.append(current_group)
        already_compared.add(i)

    not_grouped_indices = list(all_indices - already_compared)

    return similar_groups, not_grouped_indices, ssim_matrix, size_similarity_matrix


def get_size_similarity(
    img1: Image.Image,
    img2: Image.Image,
) -> float:
    """
    Calculate the size similarity between two images, returning a score between 0 and 1.

    1.0 indicates identical dimensions, values closer to 0 indicate greater disparity.

    Args:
        img1: First image to compare.
        img2: Second image to compare.

    Returns:
        A float indicating the similarity in size between the two images.
    """
    width1, height1 = img1.size
    width2, height2 = img2.size
    width_ratio = min(width1 / width2, width2 / width1)
    height_ratio = min(height1 / height2, height2 / height1)

    return (width_ratio + height_ratio) / 2


def create_striped_background(
    width: int,
    height: int,
    stripe_width: int = 10,
    colors: tuple = ("blue", "red"),
) -> Image.Image:
    """
    Create an image with diagonal stripes.

    Args:
        width (int): Width of the background image.
        height (int): Height of the background image.
        stripe_width (int): Width of each stripe.
        colors (tuple): Tuple containing two colors for the stripes.

    Returns:
        Image.Image: An image with diagonal stripes.
    """
    image = Image.new("RGB", (width, height), "black")
    draw = ImageDraw.Draw(image)
    stripe_color = 0
    for i in range(-height, width + height, stripe_width):
        draw.polygon(
            [
                (i, 0),
                (i + stripe_width, 0),
                (i + height + stripe_width, height),
                (i + height, height)
            ],
            fill=colors[stripe_color],
        )
        stripe_color = 1 - stripe_color  # Switch between 0 and 1 to alternate colors
    return image


def plot_similar_image_groups(
    masked_images: list[Image.Image],
    groups: list[list[int]],
    ssim_values: list[list[float]],
    border_size: int = 5,
    margin: int = 10,
) -> None:
    """
    Create and display a composite image for each group of similar images in a grid layout,
    with diagonal stripe pattern as background and a border around each image.

    Args:
        masked_images (list[Image.Image]): list of images to be grouped.
        groups (list[list[int]]): list of lists, where each sublist contains indices
                                  of similar images.
        ssim_values (list[list[float]]): SSIM matrix with the values between images.
        border_size (int): Size of the border around each image.
        margin (int): Margin size in pixels between images in the composite.
    """
    for group in groups:
        images_to_combine = [masked_images[idx] for idx in group]

        # Determine the grid size
        n = len(images_to_combine)
        grid_size = math.ceil(math.sqrt(n))
        max_width = max(img.width for img in images_to_combine)
        max_height = max(img.height for img in images_to_combine)

        # Calculate the dimensions of the composite image
        composite_width = grid_size * max_width + (grid_size - 1) * margin
        composite_height = grid_size * max_height + (grid_size - 1) * margin + 50  # Extra space for title

        # Create striped background
        background = create_striped_background(composite_width, composite_height)

        #composite_image = Image.new('RGB', (composite_width, composite_height), 'black')
        composite_image = Image.new('RGBA', (composite_width, composite_height), (0, 0, 0, 0))
        composite_image.paste(background, (0, 0))

        draw = ImageDraw.Draw(composite_image)
        font = ImageFont.load_default()

        # Calculate min and max SSIM
        min_ssim = min(ssim_values[i][j] for i in group for j in group if i != j)
        max_ssim = max(ssim_values[i][j] for i in group for j in group if i != j)
        title_lines = [
            f"{len(group)=}",
            f"{min_ssim=:.4f}",
            f"{max_ssim=:.4f}",
        ]
        for i, title_line in enumerate(title_lines):
            draw.text((10, 10*i + 10), title_line, font=font, fill='white')

        # Place images in a grid
        x, y = 0, 50  # Start below title space
        for idx, img in enumerate(images_to_combine):
            composite_image.paste(img, (x, y), mask=img)
            x += max_width + margin
            if (idx + 1) % grid_size == 0:
                x = 0
                y += max_height + margin

        # Display the composite image
        composite_image.show()


"""
# XXX TODO broken, unused
def filter_ui_components(
    masks: list[np.ndarray],
    area_threshold: tuple[float, float] | None = None,
    aspect_ratio_threshold: tuple[float, float] | None = None,
    extent_threshold: float | None = None,
    solidity_threshold: float | None = None,
) -> list[np.ndarray]:
    filtered_masks = []

    for mask in masks:
        mask_uint8 = mask.astype(np.uint8) * 255
        contours, _ = cv2.findContours(
            mask_uint8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        for contour in contours:
            area = cv2.contourArea(contour)

            if area_threshold is not None and (
                area < area_threshold[0] or area > area_threshold[1]
            ):
                continue

            x, y, w, h = cv2.boundingRect(contour)
            aspect_ratio = float(w) / h

            if aspect_ratio_threshold is not None and (
                aspect_ratio < aspect_ratio_threshold[0]
                or aspect_ratio > aspect_ratio_threshold[1]
            ):
                continue

            bounding_rect_area = w * h
            extent = area / bounding_rect_area if bounding_rect_area > 0 else 0

            if extent_threshold is not None and extent < extent_threshold:
                continue

            hull = cv2.convexHull(contour)
            hull_area = cv2.contourArea(hull)
            solidity = area / hull_area if hull_area > 0 else 0

            if solidity_threshold is not None and solidity < solidity_threshold:
                continue

            contour_mask = np.zeros(mask.shape, dtype=np.uint8)
            cv2.drawContours(
                contour_mask, [contour], -1, color=255, thickness=cv2.FILLED
            )
            filtered_masks.append(contour_mask)
    return filtered_masks
"""
