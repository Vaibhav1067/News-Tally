/* Sequential ramps for the India map: one hue each, light to dark. Bins are fixed thresholds because a
   few states sit far above the rest and would flatten a linear scale. */
export const BINS = [
  { max: 150, fill: '#f6d8ce', label: 'Under 150', short: 'under 150' },
  { max: 250, fill: '#efb5a4', label: '150 to 250', short: '150' },
  { max: 350, fill: '#e38a75', label: '250 to 350', short: '250' },
  { max: 500, fill: '#cf5c4b', label: '350 to 500', short: '350' },
  { max: 800, fill: '#ad2f2b', label: '500 to 800', short: '500' },
  { max: Infinity, fill: '#7a0f16', label: 'Over 800', short: '800 and over' },
]
export const fillFor = (rate: number) => BINS.find((b) => rate < b.max)!.fill

/* Fact-checked claims naming the state. Zero is a neutral grey: no data, not a low value. */
export const CLAIM_BINS = [
  { max: 1, fill: '#e6e6e1', label: 'None', short: 'none' },
  { max: 25, fill: '#d3e0f4', label: '1 to 24', short: '1' },
  { max: 75, fill: '#a9c4ea', label: '25 to 74', short: '25' },
  { max: 150, fill: '#739edc', label: '75 to 149', short: '75' },
  { max: 250, fill: '#3d74c7', label: '150 to 249', short: '150' },
  { max: Infinity, fill: '#174a96', label: '250 and over', short: '250 and over' },
]
export const claimFill = (n: number) => CLAIM_BINS.find((b) => n < b.max)!.fill
export const rate1 = new Intl.NumberFormat('en-IN', { minimumFractionDigits: 1, maximumFractionDigits: 1 })

