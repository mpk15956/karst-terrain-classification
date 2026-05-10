# GEOG 6591: Final Project Research Proposal

## Question

Can Topological Data Analysis (TDA) features serve as a computationally efficient and predictively powerful alternative to traditional geomorphology metrics for classifying surficial geology from Digital Elevation Models (DEMs)?

How do these compact, mathematically-derived topological features (e.g., Persistence Images) compare, in terms of predictive power and semantic alignment, to the high-dimensional features extracted by a pre-trained computer vision model? I aim to use TDA as an interpretable and efficient feature-extraction method that bridges the gap between slow, traditional features and opaque, black-box deep learning models.

## Data

We plan to use an existing, AI-ready DEM dataset covering Warren and Hardin Counties, Kentucky, which is an ideal, topologically complex region for this study, as it is home to Mammoth Cave National Park.

- Input Data (Features): The raw data consists of Digital Elevation Model (DEM) tiles in a raster image format.
- Output Data (Labels): The labels indicate the presence or absence of seven different types of surficial geologic deposits (e.g., Qal - Alluvium, Qr - Residuum), making this a multi-label classification problem.
- We will generate four distinct feature sets from the raw DEMs:

 1. The flattened DEM matrix, which is a vector of elevation values.
 2. Traditional Metrics: Geomorphological features (e.g., slope, aspect).
 3. TDA Metrics: Topological features (e.g., Betti Curves, Persistence Images) generated with giotto-tda.
 4. Pre-trained AI Features: A relevant 3-channel input (e.g., Channel 1: Elevation, Channel 2: Slope, Channel 3: Aspect) will be fed into a pre-trained model from Hugging Face to extract features.

## Evaluation

1. Predictive Performance: The primary metric will be the F1-macro score, which is well-suited for this imbalanced, multi-label classification task. We will use spatial cross-validation rather than random CV to obtain an assessment of model performance in a geographic context.
2. We will use a TOST (Two One-Sided Tests) for equivalence to test whether the TDA model's performance is statistically interchangeable with that of the other models. The equivalence margin (δ) will be rigorously defined a priori as a fraction (e.g., 0.25) of the baseline model's stable, spatial standard deviation.
3. Qualitative Alignment: To measure "semantic alignment," I will use a symmetric attribution framework of what each model learned by visualizing whether the TDA, Traditional, and AI models prioritize the same underlying geomorphological features.
