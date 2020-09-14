library(tidyverse)
library(ggthemes)
library(cetcolor)
library(ggmap)
library(gridExtra)

# constants
# from cetcolor::cet_pal(8, 'c2s')
colors=c("#2E22EA","#9E3DFB","#F86BE2","#FCCE7B",
         "#C4E416","#4BBA0F","#447D87","#2C24E9"
)

# functions
direction_labeller <- function(x){
  ifelse(
    x %% 45 == 0, 
    c('E','NE','N','NW','W','SW','S','SE')[1+(as.integer(x/45) %% 8)], 
    ''
  )
}

# create compasses
hues_df = data.frame(degree = 0:359) %>%
  mutate(
    label=direction_labeller((degree+90) %% 360),
    colors = colorRampPalette(cet_pal(8,'c2'))(360)
  )

color_compass = ggplot(hues_df) + 
  geom_rect(
    aes(ymin=3,ymax=4, xmin=degree-0.5,xmax=degree+0.5,color=colors,fill=colors)
  ) + coord_polar(direction=-1, start=0) +
  scale_color_identity() + 
  scale_fill_identity() +
  guides(fill=FALSE,color=FALSE) + 
  theme_void() + 
  ylim(c(1,4.5)) + 
  geom_text(
    aes(x=degree,y=4.5,label=label) 
  )
