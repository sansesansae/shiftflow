"use client";

import { createTheme } from "@mui/material/styles";

const portalContainer = () =>
  typeof document !== "undefined"
    ? document.getElementById("__next") ?? document.body
    : null;

const theme = createTheme({
  cssVariables: true,
  shape: {
    borderRadius: 20,
  },
  palette: {
    primary: {
      main: "#c7562a",
      light: "#df7c54",
      dark: "#9f431e",
      contrastText: "#fffaf5",
    },
    secondary: {
      main: "#0d6efd",
      light: "#4a8dfd",
      dark: "#084db0",
      contrastText: "#f8fbff",
    },
    background: {
      default: "#f3ede3",
      paper: "#fffdf9",
    },
    text: {
      primary: "#211b14",
      secondary: "#6d6257",
    },
  },
  typography: {
    fontFamily:
      'var(--font-manrope), "Inter", "Helvetica Neue", Arial, sans-serif',
    h1: {
      fontWeight: 700,
      letterSpacing: "-0.04em",
    },
    h2: {
      fontWeight: 700,
      letterSpacing: "-0.03em",
    },
    h3: {
      fontWeight: 600,
      letterSpacing: "-0.02em",
    },
    button: {
      textTransform: "none",
      fontWeight: 600,
    },
  },
  components: {
    MuiCssBaseline: {
      styleOverrides: {
        body: {
          background:
            "radial-gradient(circle at top left, rgba(235,94,40,0.16), transparent 26%), radial-gradient(circle at top right, rgba(13,110,253,0.14), transparent 24%), linear-gradient(180deg, #f9f4ec 0%, #f3efe7 42%, #efe9df 100%)",
        },
      },
    },
    MuiPaper: {
      defaultProps: {
        elevation: 0,
      },
      styleOverrides: {
        root: {
          backgroundImage: "none",
        },
      },
    },
    MuiButton: {
      styleOverrides: {
        root: {
          borderRadius: 18,
          paddingInline: 20,
          paddingBlock: 12,
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          borderRadius: 24,
        },
      },
    },
    MuiModal: {
      defaultProps: {
        container: portalContainer,
      },
    },
    MuiPopover: {
      defaultProps: {
        container: portalContainer,
      },
    },
    MuiPopper: {
      defaultProps: {
        container: portalContainer,
      },
    },
  },
});

export default theme;
