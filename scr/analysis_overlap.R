# Auswertung zu madabi: Überschnitt zu OpenAIRE und OpenAlex
# Autor: Phil Kolbe
# Letzte AEnderung: 19.11.2025

library(dplyr)
library(readr)
library(tidyr)

# Daten laden
df <- read_csv("../data/processed/unified_mannheim_metadata_cleaned_with_overlap.csv")

# 1. Gesamtauswertung
#####################
overall_counts <- df %>% 
  summarise(
    openaire_overlap = sum(`overlap openaire` == 1),
    openaire_no_overlap = sum(`overlap openaire` == 0),
    openalex_overlap = sum(`overlap openalex` == 1),
    openalex_no_overlap = sum(`overlap openalex` == 0),
    total = n()
  )

print(overall_counts)

# 2. Auswertung nach Source
############################
by_source <- df %>% 
  group_by(Source) %>% 
  summarise(
    openaire_overlap = sum(`overlap openaire` == 1),
    openaire_no_overlap = sum(`overlap openaire` == 0),
    openaire_total = n(),
    openalex_overlap = sum(`overlap openalex` == 1),
    openalex_no_overlap = sum(`overlap openalex` == 0),
    openalex_total = n()
  )

print(by_source)

# 3. Kreuztabelle OpenAIRE × OpenAlex
#####################################
cross_tab <- table(df$`overlap openaire`, df$`overlap openalex`)
print(cross_tab)


# 4. Kreuztabellen OpenAIRE × OpenAlex nach Source
##################################################
cross_tabs_by_source <- df %>%
  group_by(Source) %>%
  summarise(
    cross_tab = list(table(`overlap openaire`, `overlap openalex`))
  )

# Ausgabe pro Source
for(i in 1:nrow(cross_tabs_by_source)) {
  cat("\n\n===== Source:", cross_tabs_by_source$Source[i], "=====\n")
  print(cross_tabs_by_source$cross_tab[[i]])
}

# 5. Kombinationen
###################
combos <- df %>%
  mutate(
    category = case_when(
      `overlap openaire` == 1 & `overlap openalex` == 1 ~ "Both",
      `overlap openaire` == 1 & `overlap openalex` == 0 ~ "OpenAIRE only",
      `overlap openaire` == 0 & `overlap openalex` == 1 ~ "OpenAlex only",
      TRUE ~ "None"
    )
  ) %>%
  count(category)

print(combos)

