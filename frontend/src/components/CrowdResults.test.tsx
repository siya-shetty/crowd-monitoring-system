import { render, screen, within } from '@testing-library/react'
import { CrowdResults } from './CrowdResults'
import type { CrowdAnalysis } from '../services/apiClient'

export const crowdFixture: CrowdAnalysis = {
  schema_version:1, config:{moderate_count:5,high_count:10,very_high_count:20,trend_window_frames:10,trend_min_change:1},
  frames:[{frame_index:0,timestamp_seconds:0,observed_crowd_count:5,image_occupancy_ratio:.28,crowd_concentration:.7,crowd_level:'MODERATE',crowd_count_delta:0,crowd_trend:'stable'}],
  summary:{processed_crowd_frames:1,frames_with_observed_people:1,minimum_observed_crowd_count:5,maximum_observed_crowd_count:5,average_observed_crowd_count:5,median_observed_crowd_count:5,peak_crowd_frame:0,peak_crowd_timestamp_seconds:0,average_image_occupancy:.28,maximum_image_occupancy:.28,peak_occupancy_frame:0,peak_occupancy_timestamp_seconds:0,average_crowd_concentration:.7,maximum_crowd_concentration:.7,level_distribution:[{level:'LOW',frames:0,percentage:0},{level:'MODERATE',frames:1,percentage:100},{level:'HIGH',frames:0,percentage:0},{level:'VERY_HIGH',frames:0,percentage:0}],final_crowd_trend:'stable'},
}

test('renders observed crowd metrics with precise image-space terminology', () => {
  render(<CrowdResults analysis={crowdFixture}/>)
  expect(screen.getByText('Peak observed crowd').parentElement).toHaveTextContent('5 active tracks')
  expect(screen.getByText('Average observed crowd').parentElement).toHaveTextContent('5.00 active tracks')
  expect(screen.getByText('Average image occupancy').parentElement).toHaveTextContent('28.00%')
  expect(screen.getByText('Maximum image occupancy').parentElement).toHaveTextContent('28.00%')
  expect(screen.getByText(/union of tracked person bounding boxes/)).toHaveTextContent('not physical venue occupancy')
  expect(screen.getByText(/Neither metric is people/)).toBeInTheDocument()
  expect(screen.getByText(/not universal safety standards/)).toBeInTheDocument()
})

test('renders both timelines, frame data, distribution, and final trend', () => {
  render(<CrowdResults analysis={crowdFixture}/>)
  expect(screen.getByLabelText('Crowd count timeline')).toBeInTheDocument()
  expect(screen.getByLabelText('Image occupancy timeline')).toBeInTheDocument()
  const distribution = screen.getByLabelText('Crowd level distribution')
  expect(within(distribution).getByText('MODERATE').parentElement).toHaveTextContent('1 frames · 100.0%')
  expect(screen.getByText('Stable')).toBeInTheDocument()
  const table = screen.getByRole('table')
  expect(within(table).getByText('28.00')).toBeInTheDocument()
  expect(within(table).getByText('Count delta')).toBeInTheDocument()
})

test.each(['increasing','decreasing'] as const)('shows descriptive %s trend', trend => {
  render(<CrowdResults analysis={{...crowdFixture,summary:{...crowdFixture.summary,final_crowd_trend:trend}}}/>)
  expect(screen.getByText(trend.charAt(0).toUpperCase()+trend.slice(1))).toBeInTheDocument()
})

test('renders zero-person analysis without inventing people or invalid values', () => {
  const empty: CrowdAnalysis = {...crowdFixture,frames:[],summary:{...crowdFixture.summary,processed_crowd_frames:0,frames_with_observed_people:0,minimum_observed_crowd_count:0,maximum_observed_crowd_count:0,average_observed_crowd_count:0,median_observed_crowd_count:0,peak_crowd_frame:null,peak_crowd_timestamp_seconds:null,average_image_occupancy:0,maximum_image_occupancy:0,peak_occupancy_frame:null,peak_occupancy_timestamp_seconds:null,average_crowd_concentration:0,maximum_crowd_concentration:0,level_distribution:crowdFixture.summary.level_distribution.map(d=>({...d,frames:0,percentage:0}))}}
  const { container } = render(<CrowdResults analysis={empty}/>)
  expect(screen.getByText('No active anonymous person tracks were observed.')).toBeInTheDocument()
  expect(screen.getByText('Peak observed crowd').parentElement).toHaveTextContent('0 active tracks')
  expect(screen.getByText('Unavailable')).toBeInTheDocument()
  expect(container).not.toHaveTextContent(/NaN|Infinity/)
})
