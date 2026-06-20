use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Edge {
    Left,
    Right,
    Top,
    Bottom,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct Rect {
    pub x: i32,
    pub y: i32,
    pub width: u32,
    pub height: u32,
}

impl Rect {
    pub fn right(self) -> i32 {
        self.x + self.width as i32
    }

    pub fn bottom(self) -> i32 {
        self.y + self.height as i32
    }

    pub fn overlaps_vertically(self, other: Self) -> bool {
        self.y < other.bottom() && self.bottom() > other.y
    }

    pub fn overlaps_horizontally(self, other: Self) -> bool {
        self.x < other.right() && self.right() > other.x
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ScreenNode {
    pub id: String,
    pub name: String,
    pub rect: Rect,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, Default)]
pub struct Layout {
    pub screens: Vec<ScreenNode>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Transition {
    pub from: String,
    pub to: String,
    pub edge: Edge,
}

#[derive(Debug, thiserror::Error)]
pub enum LayoutError {
    #[error("screen not found: {0}")]
    ScreenNotFound(String),
    #[error("screen id already exists: {0}")]
    DuplicateScreen(String),
}

impl Layout {
    pub fn add_screen(&mut self, screen: ScreenNode) -> Result<(), LayoutError> {
        if self.screens.iter().any(|item| item.id == screen.id) {
            return Err(LayoutError::DuplicateScreen(screen.id));
        }

        self.screens.push(screen);
        Ok(())
    }

    pub fn screen(&self, id: &str) -> Option<&ScreenNode> {
        self.screens.iter().find(|screen| screen.id == id)
    }

    pub fn target_for_exit(&self, source_id: &str, edge: Edge) -> Result<Option<Transition>, LayoutError> {
        let source = self
            .screen(source_id)
            .ok_or_else(|| LayoutError::ScreenNotFound(source_id.to_owned()))?;

        let target = self
            .screens
            .iter()
            .filter(|candidate| candidate.id != source.id)
            .filter(|candidate| touches_edge(source.rect, candidate.rect, edge))
            .min_by_key(|candidate| edge_distance(source.rect, candidate.rect, edge));

        Ok(target.map(|target| Transition {
            from: source.id.clone(),
            to: target.id.clone(),
            edge,
        }))
    }
}

fn touches_edge(source: Rect, candidate: Rect, edge: Edge) -> bool {
    match edge {
        Edge::Left => candidate.right() == source.x && candidate.overlaps_vertically(source),
        Edge::Right => candidate.x == source.right() && candidate.overlaps_vertically(source),
        Edge::Top => candidate.bottom() == source.y && candidate.overlaps_horizontally(source),
        Edge::Bottom => candidate.y == source.bottom() && candidate.overlaps_horizontally(source),
    }
}

fn edge_distance(source: Rect, candidate: Rect, edge: Edge) -> i32 {
    match edge {
        Edge::Left | Edge::Right => (center_y(source) - center_y(candidate)).abs(),
        Edge::Top | Edge::Bottom => (center_x(source) - center_x(candidate)).abs(),
    }
}

fn center_x(rect: Rect) -> i32 {
    rect.x + (rect.width as i32 / 2)
}

fn center_y(rect: Rect) -> i32 {
    rect.y + (rect.height as i32 / 2)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn finds_right_neighbor() {
        let layout = Layout {
            screens: vec![
                ScreenNode {
                    id: "desk".to_owned(),
                    name: "Desk".to_owned(),
                    rect: Rect {
                        x: 0,
                        y: 0,
                        width: 1920,
                        height: 1080,
                    },
                },
                ScreenNode {
                    id: "tablet".to_owned(),
                    name: "Android tablet".to_owned(),
                    rect: Rect {
                        x: 1920,
                        y: 0,
                        width: 1200,
                        height: 800,
                    },
                },
            ],
        };

        let transition = layout
            .target_for_exit("desk", Edge::Right)
            .expect("layout lookup")
            .expect("right neighbor");

        assert_eq!(transition.to, "tablet");
    }
}
