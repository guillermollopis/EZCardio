
open_new = "Go to main import page again"

save = "Save current analysis in .h5 file"

export_results = "Create a new results file with the results of this analysis"

append_results = "Append the results of this analysis to an existing results file"

open_doc = "Open manual"

see_shortcuts = "See shortcuts for analysis"

invert_signal = "All options in the program will be restarted, the signal inverted and peaks detected again"

redetect_peaks = "R peaks will be detected again ignoring the current noise intervals"

# analysis options
noise_explanation = "Basic noise just looks for null or too high values on the ECG. \r\nThe rest of the correction look for intervals where many outliers appear in the same region. \r\nTo see more details on when defining a noise region, go to settings"

outliers_algorithm_explanation = "Detect outliers with a special algorithm. To see how it works, check the manual"

outliers_threshold_explanation = "Detect as outliers the RR intervals that has a bigger difference to the median RR than the threshold"

# manual processing shortcuts
edit_peak_shortcuts = "Add peak: left click \r\nDelete peak: right click \r\nAdd interpolation: CTRL and left click \r\nDelete peak: CTRL and right click"

edit_noise_shortcuts = "Add noise: CTRL and left click \r\nDelete noise: CTRL and right click \r\nMove noise: move to new location with SHIFT and left click \r\nMove noise extreme: move to new location with SHIFT and left click"

edit_sample_shortcuts = "Add sample: CTRL and left click \r\nDelete sample: CTRL and right click \r\nMove sample: move to new location with SHIFT and left click \r\nMove sample extreme: move to new location with SHIFT and left click"

# AnnotationConfigDialog
name = 'Fiducial name as set in annotationConfig file'
is_pinned = 'if DISABLED annotation is set on mouse click position\r\n' \
            'if ENABLED annotation might be adjusted based on other parameters'

pinned_to = 'Signal to be used as reference for annotation timestamp adjustment'
pinned_window = 'Window size to look for adjusted annotation timestamp\r\n' \
                'If no candidate is found, annotation timestamp is defined by initial mouse click'
spin_min_distance = 'How close in time two annotations can be\r\n' \
                    'If new annotation is located too close to an existing one,\r\n' \
                    ' a "duplicate annotation" message is given and no point added to the database'
key = 'Button to be pressed before LeftMouseClick to annotate not default fiducial\r\n' \
      'The default fiducial is the one on top of the list\r\n' \
      'If STICKY FIDUCIAL option is set, it is not necessary to press the button'
symbol = "One of: 'o','t','t1','t2','t3','s','p','h','+','star','d'"
symbol_colour = 'One of: r, g, b, c, m, y, k, w'