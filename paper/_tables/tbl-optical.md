| metric | RBF-MMD | FID | KID | province swap |
|---|---|---|---|---|
| topology (flow-accumulation H0) | 3.12x | -- | -- | -- |
| CLIP (hillshade) | 4.36x | 4.07x | 6.72x | 3.47x |
| CLIP (stack) | 4.30x | 2.35x | 5.03x | 2.62x |
| Inception (hillshade) | 1.70x | skipped | 1.40x | 3.20x |
| Inception (stack) | 2.68x | skipped | 2.10x | 3.74x |

: Optical contrast (test/floor). Every metric separates generated from real; the province swap is the positive control. n_real=320 (all renderable windows), n_gen=114. {#tbl-optical}
